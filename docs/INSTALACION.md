# Instalación completa en Windows

Todos los comandos parten de la raíz: la carpeta con `README.md`, `backend`, `desktop` y `scripts`. No copies entornos virtuales ni `node_modules` de otro equipo.

## 1. Programas necesarios

| Programa | Versión o condición | Uso |
|---|---|---|
| [Python](https://www.python.org/downloads/windows/) | 3.11 o 3.12, 64 bits | Backend y voz |
| [Node.js](https://nodejs.org/en/download) | 20.19+ o 22.12+, con npm | Interfaz y compilación |
| [Git para Windows](https://git-scm.com/downloads/win) | Con Git Credential Manager | Clonar y publicar |
| [FFmpeg](https://ffmpeg.org/download.html) | Binarios Windows | Conversión de audio de Vosk/RVC |
| [eSpeak NG](https://github.com/espeak-ng/espeak-ng/releases) | Instalación Windows x64 | Kokoro |
| [Ollama](https://docs.ollama.com/windows) | Opcional, con modelo descargado | Conversación local |

Activa **Add python.exe to PATH** si el instalador de Python lo ofrece. Abre una nueva consola después de instalar herramientas.

```powershell
python --version
python -c "import struct; print(struct.calcsize('P') * 8)"
node --version
npm.cmd --version
git --version
```

Python debe indicar 3.11.x o 3.12.x y 64 bits. [Vite 7](https://vite.dev/blog/announcing-vite7) establece los mínimos de Node indicados.

## 2. Abrir u obtener el proyecto

En este equipo:

```powershell
Set-Location "C:\Users\Sergio\Desktop\Asistente_Final\AsistenteModularData"
```

En otro equipo, después de publicarlo, reemplaza usuario y repositorio:

```powershell
git clone https://github.com/TU_USUARIO/Asistente_Final.git AsistenteModularData
Set-Location AsistenteModularData
```

Ese nombre de carpeta permite que la ruta de voz predeterminada sea `voice` dentro del proyecto. Si usas otro nombre, revisa el paso 5.

## 3. Instalar todas las librerías

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -CheckOnly
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

El script instala:

- `backend/.venv`: FastAPI, Uvicorn, Pydantic, Google Gen AI, HTTPX, Keyring, Edge TTS, python-docx, openpyxl, python-pptx, fpdf2 y pytest, más sus dependencias.
- `desktop/node_modules`: Electron, Vue, Three.js, Vite, TypeScript y demás paquetes fijados en `desktop/package-lock.json`, usando `npm ci`.
- `<voiceRoot>/.venv-voice`: faster-whisper, Vosk, Kokoro, NumPy, SoundFile, phonemizer-fork, espeakng-loader y dependencias transitivas, incluidas PyTorch/Transformers según su resolución.

NumPy usa marcadores de versión: 2.3.5 para Python 3.11 y 2.5.3 para Python 3.12. El resto del manifiesto está en `backend/requirements-voice-worker.txt`. Las dependencias transitivas de Python no están completamente bloqueadas.

Para elegir el intérprete:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -PythonExecutable "C:\ruta\Python312\python.exe"
```

Para empezar con chat escrito y voces en nube, sin reconocimiento ni Kokoro:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -SkipVoiceRuntime
```

En ese modo desactiva **Escuchar en segundo plano**. Las librerías de documentos se incluyen en ambos modos: no necesitas Microsoft Office. El generador PDF actual usa `C:\Windows\Fonts\arial.ttf`.

El instalador no descarga modelos ni instala programas externos. El entorno completo de voz puede ocupar varios GB.

### Alternativa: instalación manual

Si necesitas ejecutar cada etapa por separado, desde la raíz:

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
.\backend\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
Set-Location desktop
npm.cmd ci
npm.cmd run sync-avatar
Set-Location ..
```

Después de definir `$voiceRoot` en el paso 5:

```powershell
python -m venv (Join-Path $voiceRoot '.venv-voice')
$voicePython = Join-Path $voiceRoot '.venv-voice\Scripts\python.exe'
& $voicePython -m pip install --upgrade pip
& $voicePython -m pip install -r .\backend\requirements-voice-worker.txt
```

## 4. FFmpeg y eSpeak NG

Desde la página oficial de FFmpeg sigue un enlace de **Windows EXE Files**, extrae los binarios y añade la carpeta de `ffmpeg.exe` a `PATH`. Verifica con `ffmpeg -version`.

También puedes indicar su ruta antes de iniciar la app:

```powershell
$env:ASISTENTE_FFMPEG_PATH = "C:\Herramientas\ffmpeg\bin\ffmpeg.exe"
```

Para Kokoro instala eSpeak NG x64. El trabajador espera exactamente:

```text
C:\Program Files\eSpeak NG\libespeak-ng.dll
C:\Program Files\eSpeak NG\espeak-ng-data\
```

Un paquete Python no sustituye esa instalación nativa. Edge TTS no necesita eSpeak NG.

## 5. Ruta de voz

Desde la raíz del proyecto:

```powershell
$voiceRoot = if ($env:ASISTENTE_VOICE_ROOT) {
    [IO.Path]::GetFullPath($env:ASISTENTE_VOICE_ROOT)
} else {
    [IO.Path]::GetFullPath((Join-Path (Get-Location).Path '..\AsistenteModularData\voice'))
}
New-Item -ItemType Directory -Force -Path $voiceRoot | Out-Null
Write-Output $voiceRoot
```

Coincide con el instalador y el backend. Para otra ubicación define `ASISTENTE_VOICE_ROOT` **antes de instalar y antes de ejecutar**:

```powershell
$env:ASISTENTE_VOICE_ROOT = "D:\ModelosAsistente\voice"
```

Esa asignación dura mientras permanezca abierta la consola. Para persistirla:

```powershell
[Environment]::SetEnvironmentVariable('ASISTENTE_VOICE_ROOT', 'D:\ModelosAsistente\voice', 'User')
```

Abre otra consola tras persistirla. `ASISTENTE_DATA_DIR` cambia datos personales, no la carpeta de voz.

## 6. Modelo Vosk español

Consulta [Vosk Models](https://alphacephei.com/vosk/models). Con `$voiceRoot` definido:

```powershell
$voskRoot = Join-Path $voiceRoot 'models\vosk'
New-Item -ItemType Directory -Force -Path $voskRoot | Out-Null
$voskZip = Join-Path $voiceRoot 'vosk-model-small-es-0.42.zip'
Invoke-WebRequest -Uri 'https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip' -OutFile $voskZip
Expand-Archive -LiteralPath $voskZip -DestinationPath $voskRoot -Force
```

La estructura final debe incluir `<voiceRoot>\models\vosk\vosk-model-small-es-0.42\am\final.mdl`; evita una carpeta duplicada al extraer.

## 7. Modelo faster-whisper

El predeterminado es `small` para CPU. Se descarga al usarlo por primera vez. Para prepararlo antes:

```powershell
$voicePython = Join-Path $voiceRoot '.venv-voice\Scripts\python.exe'
$whisperRoot = Join-Path $voiceRoot 'models\whisper'
& $voicePython -c "import sys; from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8', download_root=sys.argv[1])" $whisperRoot
```

Consulta [faster-whisper](https://github.com/SYSTRAN/faster-whisper). El backend admite `ASISTENTE_STT_MODEL`, `ASISTENTE_STT_CPU_THREADS`, `ASISTENTE_STT_BEAM_SIZE` y `ASISTENTE_VOSK_MODEL`.

## 8. Kokoro local (opcional)

Descarga del [repositorio de hexgrad](https://huggingface.co/hexgrad/Kokoro-82M/tree/main):

```powershell
$kokoroRoot = Join-Path $voiceRoot 'models\kokoro'
New-Item -ItemType Directory -Force -Path $kokoroRoot | Out-Null
Invoke-WebRequest -Uri 'https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/kokoro-v1_0.pth' -OutFile (Join-Path $kokoroRoot 'kokoro-v1_0.pth')
Invoke-WebRequest -Uri 'https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/config.json' -OutFile (Join-Path $kokoroRoot 'config.json')
Invoke-WebRequest -Uri 'https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices/af_alloy.pt' -OutFile (Join-Path $kokoroRoot 'af_alloy.pt')
```

El código actual espera `af_alloy.pt` y usa idioma español (`e`). Otros recursos del motor pueden descargarse en la primera síntesis: para trabajar sin conexión hay que prepararlos y probar la síntesis antes. Selecciona **Kokoro** en Configuración → Voz.

Si solo usas Edge TTS, no necesitas los pesos de Kokoro.

## 9. Proveedores de conversación y voz

Para Gemini, obtén una clave desde [Google AI Studio](https://aistudio.google.com/), guárdala en Configuración → Credenciales y elige un modelo disponible en tu cuenta. El nombre inicial del proyecto no garantiza disponibilidad o cuota; los cargos y límites los establece el proveedor.

Para Ollama instala la aplicación y, por ejemplo:

```powershell
ollama pull llama3.2:1b
ollama list
Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags'
```

Selecciona **Ollama local**, escribe `llama3.2:1b` y pulsa **Aplicar modelo**. Es un ejemplo que coincide con el valor inicial, puedes usar otro modelo que siga instrucciones de herramientas. Si no está activo, abre Ollama; `ollama serve` sirve como alternativa cuando el servidor no está ya ejecutándose.

Ollama no requiere clave de Gemini. La recuperación de recuerdos se hace localmente al seleccionarlo. Las voces en nube y búsquedas web siguen necesitando red.

| Motor de voz | Configuración |
|---|---|
| Edge TTS | Sin clave; necesita conexión |
| ElevenLabs | Clave e identificador de voz |
| Fish Audio | Clave e identificador de referencia |
| API personalizada | Endpoint, credencial y parámetros compatibles con `voice/tts/cloud.py` |

## 10. RVC: entorno externo opcional

El repositorio no incluye el proyecto RVC, sus dependencias ni sus pesos. El instalador no puede reconstruirlo y no basta con instalar un paquete llamado `rvc`.

El adaptador espera:

```text
<voiceRoot>\rvc\.venv\Scripts\python.exe
<voiceRoot>\rvc\infer\cli.py
<raíz del proyecto>\assets\voices\prueba\HatsuneMikuOv2.pth
<raíz del proyecto>\assets\voices\prueba\added_IVF397_Flat_nprobe_1_HatsuneMikuOv2_v2.index
```

Se necesita un proyecto cuyo `infer/cli.py` acepte `--model`, `--index`, `--input`, `--output`, `--pitch`, `--f0-method` y `--index-rate`. Instala sus dependencias, recursos y versión de Python/PyTorch conforme a ese proyecto, en un entorno independiente. El adaptador actual fuerza CPU con `RVC_FORCE_CPU=1`; esta guía no promete aceleración GPU.

Activa **Voz Miku (RVC)** solo cuando tengas ese entorno compatible y los pesos con permiso de uso. El resto de funciones no necesita RVC.

## 11. Avatar e inicio

Coloca un GLB en `assets/avatars/assistant.glb`. Los avatares externos no vienen al clonar. Sin GLB se muestra un círculo animado.

```powershell
Set-Location desktop
npm.cmd run dev
```

Electron inicia automáticamente el backend de `backend/.venv`. Para otro intérprete existe `ASISTENTE_PYTHON`. No abras otro backend en el mismo puerto si Electron ya lo está iniciando. Configuración se abre desde la bandeja.

## 12. Comprobar la instalación

Desde la raíz, con `$voiceRoot` definido:

```powershell
.\backend\.venv\Scripts\python.exe -m pip check
& (Join-Path $voiceRoot '.venv-voice\Scripts\python.exe') -m pip check
& (Join-Path $voiceRoot '.venv-voice\Scripts\python.exe') -c "import faster_whisper, vosk, kokoro, numpy, soundfile; print('Voz: importaciones correctas')"
Set-Location desktop
npm.cmd run typecheck
npm.cmd run build
Set-Location ..\backend
.\.venv\Scripts\python.exe -m pytest
```

Omite las comprobaciones del trabajador si usaste `-SkipVoiceRuntime`. La compilación no produce un instalador distribuible. Último resultado de la suite: 100 aprobadas y 4 fallos relacionados con voz.

| Problema | Solución |
|---|---|
| PowerShell bloquea `npm.ps1` | Usa `npm.cmd` |
| `python` abre Store o una versión incorrecta | Usa `-PythonExecutable` con el intérprete compatible |
| No encuentra Vosk/Kokoro | Revisa `$voiceRoot`, extracción y nombres exactos |
| No encuentra FFmpeg | Reabre consola tras cambiar `PATH` o usa `ASISTENTE_FFMPEG_PATH` |
| Error eSpeak | Comprueba DLL x64 y `espeak-ng-data` en la ruta indicada |
| Ollama rechaza conexión | Comprueba que esté activo y `/api/tags` responda |
| Gemini rechaza modelo | Revisa nombre, acceso de tu cuenta, clave y cuota |
| Rutas demasiado largas | Usa una ruta de clonación corta; recrea el entorno, no lo copies |
| No aparece avatar | Añade el GLB fuente y reinicia |

Se verificó `install.ps1 -CheckOnly` y la resolución de dependencias de voz mediante `pip install --dry-run --ignore-installed` con Python 3.12 en este equipo. La simulación no instala ni prueba los motores. La instalación completa en un Windows limpio, los modelos y servicios externos no se han validado de extremo a extremo.
