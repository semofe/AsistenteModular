import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from asistente.api.routes import create_http_router
from asistente.config.settings import LLMPreferenceStore, ConversationPreferenceStore
from asistente.core.orchestrator import Orchestrator
from asistente.memory.conversation_store import ConversationStore
from asistente.providers.base import ChatProvider, GenerationResult
from asistente.providers.ollama import OllamaProvider
from asistente.storage.database import Database
from asistente.storage.migrations import migrate
from asistente.tools.file_dispatcher import FileToolService
from asistente.tools import file_operations as operations
from asistente.tools.registry import AccessToolService
from asistente.tools.websites import WebAccessService
from asistente.access.discovery_windows import sync_discovered_apps


def test_history_survives_restart_and_clear(tmp_path):
    db = Database(tmp_path/'data.sqlite3')
    migrate(db)
    migrate(db)
    store = ConversationStore(db, max_messages=4, max_tokens=100)
    store.save_turn('Hola','Respuesta')
    orch = Orchestrator(None, tmp_path/'personality.txt', conversation_store=store)
    assert [m.content for m in orch.history] == ['Hola','Respuesta']
    orch.clear_conversation()
    assert ConversationStore(db).load_history() == []


def test_history_prunes_tokens(tmp_path):
    db = Database(tmp_path/'data.sqlite3'); migrate(db)
    store = ConversationStore(db, max_messages=20, max_tokens=10)
    store.save_turn('antiguo'*10, 'viejo'*10)
    store.save_turn('nuevo','bien')
    assert [m.content for m in store.load_history()] == ['nuevo','bien']


class Provider(ChatProvider):
    async def generate(self, messages):
        return GenerationResult(text=json.dumps({'tool':'create_file','name':'prueba','path':'escritorio','file_type':'txt','content':'Hola'}))


def test_orchestrator_file_action_waits_for_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    (tmp_path/'Desktop').mkdir()
    orch = Orchestrator(Provider(), tmp_path/'personality.txt', file_tools=FileToolService())
    reply = asyncio.run(orch.handle_text('Crea un archivo txt en escritorio'))
    assert '¿Confirmas?' in reply.text
    assert not (tmp_path/'Desktop/prueba.txt').exists()
    reply = asyncio.run(orch.handle_text('sí'))
    assert (tmp_path/'Desktop/prueba.txt').read_text() == 'Hola'
    assert 'creado' in reply.text


def test_cancel_and_expired_file_confirmations(tmp_path):
    service = FileToolService()
    payload = json.dumps({'tool':'create_folder','name':'Prueba','path':'escritorio'})
    asyncio.run(service.handle(payload))
    assert 'cancelada' in asyncio.run(service.confirm('no'))
    asyncio.run(service.handle(payload))
    service.pending = (service.pending[0], 0)
    assert 'venció' in asyncio.run(service.confirm('sí'))


@pytest.mark.parametrize('extension,content',[
    ('txt','Texto de prueba'), ('csv',{'columns':['Nombre'],'rows':[['Ana']]}),
    ('xlsx',{'columns':['Nombre'],'rows':[['Ana']]}),
    ('docx',{'title':'Título','sections':[{'paragraphs':['Texto']}]}),
    ('pptx',{'title':'Título','slides':[{'title':'Una','bullets':['Texto']}]}),
    ('pdf',{'title':'Título','sections':[{'heading':'Sección','paragraphs':['Uno','Dos'],'bullets':['Tres']}]}),
])
def test_generate_documents_and_preserve_existing(tmp_path, monkeypatch, extension, content):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    (tmp_path/'Documents').mkdir()
    result = operations.create_file_local('prueba','documentos',extension,content)
    assert 'creado' in result, result
    output = tmp_path/'Documents'/f'prueba.{extension}'
    assert output.stat().st_size > 0
    before=output.read_bytes()
    assert operations.create_file_local('prueba','documentos',extension,content)=='ALREADY_EXISTS'
    assert output.read_bytes()==before


def test_copy_move_rename_and_path_boundaries(tmp_path,monkeypatch):
    monkeypatch.setattr(Path,'home',lambda:tmp_path)
    desktop=tmp_path/'Desktop';desktop.mkdir()
    docs=tmp_path/'Documents';docs.mkdir()
    original=desktop/'original.txt';original.write_text('contenido')
    assert 'copié' in operations.copy_item_local(str(original),str(docs))
    assert 'renombré' in operations.rename_item_local(str(docs/'original.txt'),'otro.txt')
    assert 'moví' in operations.move_item_local(str(docs/'otro.txt'),str(desktop))
    assert not (docs/'otro.txt').exists()
    assert not operations.is_safe_path(tmp_path/'Windows/file.txt')
    assert 'permiso' in operations.create_folder_local('fuera',str(tmp_path))
    assert operations.check_invalid_chars('..')
    assert operations.check_invalid_chars('CON.txt')


def test_search_platform_without_model():
    web=WebAccessService(None)
    service=AccessToolService(None,web_tools=web)
    with patch.object(web,'open_search',return_value=True) as opened:
        reply=service.handle('Busca música en Spotify','Asistente')
    opened.assert_called_once_with('spotify','música')
    assert reply.handled


@pytest.mark.parametrize("query,url,confirm", [
    ("LinkedIn", "https://www.linkedin.com/", False),
    ("Mercado Libre", "https://www.mercadolibre.com.pe/", False),
    ("Instagram", "https://www.instagram.com/", False),
    ("linkndin", "https://www.linkedin.com/", True),
    ("instgram", "https://www.instagram.com/", True),
    ("example.org", "https://example.org", False),
    ("Sitio desconocido", "https://www.google.com/search?q=Sitio%20desconocido", False),
])
def test_enter_without_registered_website(query, url, confirm):
    web = WebAccessService(None)
    service = AccessToolService(None, web_tools=web)
    with patch.object(web, "_open") as open_browser, patch(
        "asistente.tools.websites._search_website", return_value=None
    ):
        reply = service.handle(f"Entra a {query}", "Asistente")
        assert reply.handled
        if confirm:
            assert service.pending_website is not None
            open_browser.assert_not_called()
            service.handle("confirmo", "Asistente")
        open_browser.assert_called_once_with(url)


@pytest.mark.parametrize("second_result,expected", [
    ("https://www.wikipedia.org/wiki/Example", "https://es.wikipedia.org/"),
    ("https://wikipedia.org.evil.com/", "https://es.wikipedia.org/"),
    ("https://wikipedia.com/", "https://www.google.com/search?q=Wikipedia"),
])
def test_enter_uses_unique_web_search_domain(second_result, expected):
    response = httpx.Response(
        200,
        text=(
            "<rss><channel><item><link>https://es.wikipedia.org/wiki/Main</link></item>"
            f"<item><link>{second_result}</link></item></channel></rss>"
        ),
        request=httpx.Request("GET", "https://www.bing.com/search"),
    )
    web = WebAccessService(None)
    service = AccessToolService(None, web_tools=web)
    with patch.object(web, "_open") as open_browser, patch(
        "asistente.tools.websites.httpx.get", return_value=response
    ) as search:
        assert service.handle("Entra a Wikipedia", "Asistente").handled
        assert search.call_args.kwargs["params"] == {"q": "Wikipedia", "format": "rss"}
        open_browser.assert_called_once_with(expected)


def test_discovery_preserves_registered_apps():
    catalog=SimpleNamespace(resolve=lambda name: object() if name=='Existente' else None)
    with patch('asistente.access.discovery_windows.discover_start_menu_apps',return_value=[{'name':'Existente'},{'name':'Nueva'}]), patch.object(catalog,'add',create=True) as add:
        assert sync_discovered_apps(catalog)==1
        add.assert_called_once_with(name='Nueva')


def test_ollama_payload_and_token_count():
    from asistente.providers.base import ChatMessage
    async def request(self,url,*,json):
        assert url=='http://127.0.0.1:11434/api/chat'
        assert json['model']=='modelo'
        assert json['messages'][0]['content']=='Hola'
        return httpx.Response(200,json={'message':{'content':'Respuesta'},'prompt_eval_count':5,'eval_count':2},request=httpx.Request('POST',url))
    with patch.object(httpx.AsyncClient,'post',request):
        result=asyncio.run(OllamaProvider('modelo').generate([ChatMessage('user','Hola')]))
    assert result.total_tokens==7
    assert result.text=='Respuesta'


def test_llm_configuration_applies_without_restart(tmp_path):
    credentials=SimpleNamespace(get=lambda provider:'test-api-key',set=lambda *args:None)
    voice=SimpleNamespace(credentials=credentials)
    orch=Orchestrator(None,tmp_path/'personality.txt')
    store=LLMPreferenceStore(tmp_path/'llm.json')
    app=FastAPI()
    app.include_router(create_http_router(voice,tmp_path/'voice',orchestrator=orch,llm_preferences=store,conversation_preferences=ConversationPreferenceStore(tmp_path/'conversation.json')))
    with TestClient(app) as client:
        response=client.put('/api/llm/config',json={'provider':'ollama','gemini_model':'gemini-test','ollama_model':'local-test'})
        assert response.status_code==200
        assert isinstance(orch.provider,OllamaProvider)
        assert orch.provider.model=='local-test'
        assert client.put('/api/voice/credentials/gemini',json={'api_key':'new-test-key'}).status_code==200
        assert isinstance(orch.provider,OllamaProvider)
        assert client.put('/api/llm/config',json={'provider':'invalid','gemini_model':'x','ollama_model':'y'}).status_code==422

@pytest.mark.parametrize('command,expected',[
    ('Pon música tranquila',('youtube','música tranquila')),
    ('Oye Asistente, busca noticias en Google por favor',('google','noticias')),
    ('Puedes poner jazz en Spotify?',('spotify','jazz')),
    ('Busca archivos PDF',None),
    ('Entra a linkndin',('website','linkndin')),
    ('Entra Mercado Libre',('website','Mercado Libre')),
    ('Oye Asistente, entra en instgram por favor',('website','instgram')),
    ('Entra a',None),
    ('Abre Instagram',None),
])
def test_platform_search_variants(command,expected):
    from asistente.tools.websites import parse_platform_search
    assert parse_platform_search(command,'Asistente')==expected
