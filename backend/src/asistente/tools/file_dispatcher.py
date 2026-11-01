"""File tools selected by the model; execution and confirmations stay local."""
from __future__ import annotations

import asyncio
import json
import re
from time import monotonic
from typing import Literal, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from asistente.tools.file_operations import (
    create_folder_local, create_file_local, move_item_local, copy_item_local, rename_item_local,
)
from asistente.tools.search import search_files_local

TOOL_INSTRUCTIONS = '''Cuando el usuario solicite buscar, crear, copiar, mover o renombrar archivos o carpetas,
responde SOLO con un objeto JSON de herramienta. Nunca inventes resultados.
Herramientas y campos:
{"tool":"search_files","query":"informe","extension":"pdf","location":"documentos"}
{"tool":"create_folder","name":"Trabajo","path":"escritorio"}
{"tool":"create_file","name":"informe","path":"documentos","file_type":"docx","content":{"title":"Informe","sections":[{"heading":"Resumen","paragraphs":["Texto"],"bullets":["Punto"]}]}}
{"tool":"move_item","source":"ruta o nombre","destination":"ruta o carpeta conocida"}
{"tool":"copy_item","source":"ruta o nombre","destination":"ruta o carpeta conocida"}
{"tool":"rename_item","source":"ruta o nombre","new_name":"nombre nuevo"}
Formatos: txt (content texto), csv/xlsx (content {"columns":[],"rows":[[]]}),
docx/pdf (content texto o title/sections), pptx (content {"title":"...","slides":[{"title":"...","bullets":[]}]}).
Ubicaciones: escritorio, documentos, descargas, imagenes, videos, musica o rutas absolutas.
Si falta nombre, ubicación o el elemento original, pregunta por el dato que falta.
Estas herramientas no leen documentos. Para leer o resumir, responde usando el contenido autorizado recibido.
Para otras peticiones, responde normalmente sin JSON.'''

class FileToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: Literal["search_files", "create_folder", "create_file", "move_item", "copy_item", "rename_item"]
    query: str | None = Field(default=None, max_length=300)
    extension: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=1000)
    name: str | None = Field(default=None, max_length=180)
    path: str | None = Field(default=None, max_length=1000)
    source: str | None = Field(default=None, max_length=1000)
    destination: str | None = Field(default=None, max_length=1000)
    new_name: str | None = Field(default=None, max_length=180)
    file_type: Literal["txt", "csv", "docx", "xlsx", "pptx", "pdf"] | None = None
    content: Any = None

class FileToolService:
    def __init__(self) -> None:
        self.pending: tuple[FileToolCall, float] | None = None
        self.awaiting_details = False

    @staticmethod
    def is_request(text: str) -> bool:
        return bool(re.search(r"\b(busca|buscar|encuentra|localiza|crea|crear|genera|generar|redacta|copia|copiar|mueve|mover|renombra|renombrar)\b", text, re.I))

    async def confirm(self, text: str) -> str | None:
        if self.pending is None:
            return None
        call, expires = self.pending
        self.awaiting_details = False
        self.pending = None
        if monotonic() > expires:
            return "La confirmación de archivos venció. Solicita de nuevo la operación."
        answer = text.strip().lower().strip(' .!')
        if answer in ("sí", "si", "confirmo", "adelante", "hazlo", "si hazlo", "sí hazlo", "correcto"):
            return await self.execute(call)
        if answer in ("no", "cancela", "cancelar", "no gracias", "déjalo", "dejalo"):
            return "Operación de archivos cancelada."
        return None

    async def handle(self, text: str) -> str | None:
        raw = text.strip()
        if raw.startswith('```'):
            raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw)
        if not raw.startswith('{'):
            self.awaiting_details = '?' in raw or '¿' in raw
            if re.match(r"^(?:¡?hecho|listo|he creado|he movido|he copiado|he renombrado)\b", raw, re.I):
                return "No recibí una operación de archivos válida. Indica la acción, el nombre y la ubicación."
            return None
        self.awaiting_details = False
        try:
            call = FileToolCall.model_validate_json(raw)
        except (ValidationError, ValueError):
            return "No pude validar la operación de archivos. Indica el nombre y la ubicación."
        if call.tool == 'search_files':
            return await self.execute(call)
        required = {
            'create_folder': ('name','path'), 'create_file': ('name','path','file_type'),
            'move_item': ('source','destination'), 'copy_item': ('source','destination'),
            'rename_item': ('source','new_name'),
        }[call.tool]
        if any(not getattr(call, field) for field in required):
            return "Faltan datos. Indica el nombre del archivo o carpeta y su ubicación."
        if call.tool == 'create_file' and call.content is not None:
            if call.file_type in ('csv', 'xlsx', 'pptx') and not isinstance(call.content, dict):
                return "El contenido no tiene el formato necesario para ese tipo de archivo."
            if call.file_type in ('docx', 'pdf') and not isinstance(call.content, (dict, str)):
                return "El contenido del documento debe ser texto o secciones."
        if len(json.dumps(call.content, ensure_ascii=False)) > 100_000:
            return "El contenido solicitado supera el límite de generación."
        # Show the concrete operation before changing files.
        self.pending = (call, monotonic() + 120)
        details = {key: getattr(call, key) for key in required}
        action = {'create_folder':'crear carpeta','create_file':'crear archivo','move_item':'mover','copy_item':'copiar','rename_item':'renombrar'}[call.tool]
        preview = ""
        if call.content is not None:
            preview = "\nContenido: " + json.dumps(call.content, ensure_ascii=False)[:1200]
        return f"Voy a {action}: " + "; ".join(f"{key}: {value}" for key,value in details.items()) + preview + "\n¿Confirmas?"

    async def execute(self, call: FileToolCall) -> str:
        try:
            if call.tool == 'search_files':
                results = await asyncio.wait_for(asyncio.to_thread(search_files_local, call.query, call.extension, call.location), timeout=10)
                return "No encontré archivos coincidentes." if not results else "Archivos encontrados:\n" + "\n".join(f"- {item['name']} — {item['path']}" for item in results)
            if call.tool == 'create_folder':
                return await asyncio.to_thread(create_folder_local, call.name, call.path)
            if call.tool == 'create_file':
                result = await asyncio.to_thread(create_file_local, call.name, call.path, call.file_type, call.content)
                return "Ya existe ese archivo. Indica otro nombre para crear una nueva versión." if result == 'ALREADY_EXISTS' else result
            if call.tool == 'rename_item':
                return await asyncio.to_thread(rename_item_local, call.source, call.new_name)
            operation = move_item_local if call.tool == 'move_item' else copy_item_local
            return await asyncio.to_thread(operation, call.source, call.destination)
        except asyncio.TimeoutError:
            return "La búsqueda tardó demasiado. Indica una ubicación más concreta."
        except (OSError, ValueError, TypeError, ImportError) as exc:
            return f"No pude completar la operación de archivos: {exc}"
