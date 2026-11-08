"""Trabajador ejecutado dentro del entorno que contiene los modelos de voz."""

from __future__ import annotations

import argparse
import ctypes
from collections.abc import Iterator
import json
import wave
from pathlib import Path


def audio_pcm(path: str, sample_rate: int) -> Iterator[bytes]:
    from av import AudioResampler, open as open_audio

    resampler = AudioResampler(format="s16", layout="mono", rate=sample_rate)
    with open_audio(path) as audio:
        for frame in audio.decode(audio=0):
            for converted in resampler.resample(frame):
                yield converted.to_ndarray().tobytes()
        for converted in resampler.resample(None):
            yield converted.to_ndarray().tobytes()


def normalize_audio(args: argparse.Namespace) -> None:
    with wave.open(args.output, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(args.sample_rate)
        for pcm in audio_pcm(args.input, args.sample_rate):
            output.writeframesraw(pcm)


def transcribe(args: argparse.Namespace) -> None:
    import numpy as np
    from faster_whisper import WhisperModel

    samples = np.frombuffer(b"".join(audio_pcm(args.input, 16000)), dtype="<i2")
    if not samples.size:
        print(json.dumps({"text": ""}))
        return

    local_model = Path(args.model_root) / f"faster-whisper-{args.model}"
    model_source = str(local_model) if (local_model / "model.bin").is_file() else args.model
    model = WhisperModel(
        model_source,
        device=args.device,
        compute_type=args.compute_type,
        cpu_threads=args.cpu_threads,
        download_root=args.model_root,
    )
    segments, _ = model.transcribe(
        samples.astype(np.float32) / 32768,
        language=args.language,
        beam_size=args.beam_size,
        vad_filter=True,
        hotwords=args.hotwords or None,
    )
    text = " ".join(segment.text.strip() for segment in segments).strip()
    print(json.dumps({"text": text}, ensure_ascii=False))


def transcribe_vosk(args: argparse.Namespace) -> None:
    from vosk import KaldiRecognizer, Model, SetLogLevel

    SetLogLevel(-1)
    grammar = json.loads(Path(args.grammar).read_text(encoding="utf-8"))
    if not isinstance(grammar, list) or not grammar:
        raise ValueError("El vocabulario de Vosk está vacío.")
    model = Model(args.model)
    recognizer = KaldiRecognizer(model, args.sample_rate, json.dumps(grammar, ensure_ascii=False))
    recognizer.SetWords(True)
    results = []
    for pcm in audio_pcm(args.input, args.sample_rate):
        if recognizer.AcceptWaveform(pcm):
            results.append(json.loads(recognizer.Result()))
    results.append(json.loads(recognizer.FinalResult()))
    words = [word for result in results for word in result.get("result", [])]
    text = " ".join(result["text"] for result in results if result.get("text"))
    confidence = (
        sum(float(word.get("conf", 0.0)) for word in words) / len(words)
        if words
        else 0.0
    )
    print(
        json.dumps(
            {"text": text, "confidence": confidence},
            ensure_ascii=False,
        )
    )


def synthesize(args: argparse.Namespace) -> None:
    import numpy as np
    import soundfile as sf
    from kokoro import KModel, KPipeline
    from phonemizer.backend.espeak import api as espeak_api
    from phonemizer.backend.espeak.wrapper import EspeakWrapper

    # Phonemizer copia la DLL a %TEMP% para soportar varias instancias. Asistente Modular usa
    # un proceso aislado con una sola instancia, así que puede cargarla
    # directamente y evita fallos de permisos frecuentes en Windows.
    def initialize_espeak(api: object, library: str, data_path: str | None) -> None:
        api._library_path = Path(library)  # type: ignore[attr-defined]
        api._tempdir = None  # type: ignore[attr-defined]
        api._library = ctypes.cdll.LoadLibrary(str(library))  # type: ignore[attr-defined]
        encoded_data = str(data_path).encode("utf-8") if data_path else None
        if api._library.espeak_Initialize(0x02, 0, encoded_data, 0) <= 0:  # type: ignore[attr-defined]
            raise RuntimeError("No se pudo inicializar eSpeak NG.")

    espeak_api.EspeakAPI.__init__ = initialize_espeak
    espeak_api.EspeakAPI._delete_win32 = lambda _self: None

    EspeakWrapper.set_library(r"C:\Program Files\eSpeak NG\libespeak-ng.dll")
    EspeakWrapper.set_data_path(r"C:\Program Files\eSpeak NG\espeak-ng-data")
    model = KModel(config=args.config, model=args.model)
    pipeline = KPipeline(lang_code=args.language, model=model, repo_id="hexgrad/Kokoro-82M")
    chunks = [audio.numpy() for _, _, audio in pipeline(args.text, voice=args.voice, speed=1.0)]
    if not chunks:
        raise RuntimeError("Kokoro no generó audio.")
    sf.write(args.output, np.concatenate(chunks), 24000)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    stt = subparsers.add_parser("transcribe")
    stt.add_argument("--input", required=True)
    stt.add_argument("--model", default="base")
    stt.add_argument("--model-root", required=True)
    stt.add_argument("--hotwords", default="")
    stt.add_argument("--device", default="cpu")
    stt.add_argument("--compute-type", default="int8")
    stt.add_argument("--language", default="es")
    stt.add_argument("--beam-size", type=int, default=5)
    stt.add_argument("--cpu-threads", type=int, default=6)
    stt.set_defaults(handler=transcribe)
    vosk = subparsers.add_parser("transcribe-vosk")
    vosk.add_argument("--input", required=True)
    vosk.add_argument("--model", required=True)
    vosk.add_argument("--grammar", required=True)
    vosk.add_argument("--sample-rate", type=int, default=16000)
    vosk.set_defaults(handler=transcribe_vosk)
    normalize = subparsers.add_parser("normalize-audio")
    normalize.add_argument("--input", required=True)
    normalize.add_argument("--output", required=True)
    normalize.add_argument("--sample-rate", type=int, required=True)
    normalize.set_defaults(handler=normalize_audio)
    tts = subparsers.add_parser("synthesize")
    tts.add_argument("--text", required=True)
    tts.add_argument("--output", required=True)
    tts.add_argument("--model", required=True)
    tts.add_argument("--config", required=True)
    tts.add_argument("--voice", required=True)
    tts.add_argument("--language", default="e")
    tts.set_defaults(handler=synthesize)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
