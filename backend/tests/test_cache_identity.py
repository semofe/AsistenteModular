from dataclasses import replace

from asistente.voice.cache import AudioCache
from asistente.voice.manager import VoiceManager
from asistente.voice.tts.edge import EdgeTTSSettings


def test_different_sentences_never_reuse_the_same_audio_key():
    assert AudioCache.key('Hola', {}) != AudioCache.key('Perdón, ¿puedes repetirlo?', {})


def test_edge_setting_changes_invalidate_cached_audio():
    manager = VoiceManager.__new__(VoiceManager)
    manager.edge = EdgeTTSSettings()
    first = manager._cache_configuration('edge', None, None, False)
    manager.edge = replace(manager.edge, pitch='+10Hz')
    second = manager._cache_configuration('edge', None, None, False)
    assert AudioCache.key('Hola', first) != AudioCache.key('Hola', second)


def test_normal_conversation_after_wake_is_not_rejected():
    from asistente.automation.local_parser import is_likely_conversation_after_wake

    for text in ['Oye Asistente Modular estoy cansado', 'Oye Asistente Modular me gusta este modelo', 'Oye Asistente Modular tengo una pregunta']:
        assert is_likely_conversation_after_wake(text, 'Asistente Modular')
    assert not is_likely_conversation_after_wake('Oye Asistente Modular si arrastim', 'Asistente Modular')
