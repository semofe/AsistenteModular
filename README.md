# Asistente Modular

Asistente para Windows con Electron, Vue 3, Three.js y backend Python/FastAPI. Combina Gemini u Ollama, comandos locales, memoria, voz y un avatar 3D opcional.

## Guías

- [Instalación completa, dependencias y modelos](docs/INSTALACION.md)
- [Subir este proyecto a GitHub paso a paso](docs/GITHUB.md)

## Requisitos

- Windows de 64 bits y Python **3.11 o 3.12 de 64 bits**.
- Node.js **20.19+ o 22.12+**, con npm; son los mínimos que requiere Vite 7.
- Git para clonar y publicar el código.
- Para voz completa: FFmpeg, eSpeak NG y los modelos descritos en la guía.
- Ollama es opcional; necesita su propia instalación y un modelo descargado.

## Instalar y ejecutar

Abre PowerShell en la carpeta que contiene este README, `backend`, `desktop` y `scripts`:

```powershell
# En este equipo:
Set-Location "C:\Users\Sergio\Desktop\Asistente_Final\AsistenteModularData"

# Comprueba Python, Node y npm sin instalar paquetes.
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -CheckOnly

# Instala backend, herramientas de documentos, interfaz y entorno de voz.
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1

Set-Location desktop
npm.cmd run dev
```

Para chat escrito y voces en nube, sin reconocimiento ni Kokoro:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -SkipVoiceRuntime
```

En ese modo, desactiva **Escuchar en segundo plano** hasta instalar el entorno de voz. Para elegir otro intérprete pasa `-PythonExecutable "C:\ruta\Python312\python.exe"` al instalador.

El instalador se detiene cuando falla un comando. No descarga modelos Vosk/Kokoro, ni instala Ollama, FFmpeg, eSpeak NG o el proyecto externo RVC. Consulta [la instalación completa](docs/INSTALACION.md).

## Primera configuración

Abre Configuración con clic derecho en el icono de la bandeja de Windows.

1. Para Gemini, guarda la clave API y selecciona un modelo disponible en tu cuenta.
2. Para Ollama, descarga un modelo y selecciona **Ollama local** con el mismo nombre. La API se espera en `http://127.0.0.1:11434`.
3. Pulsa **Aplicar modelo**; cambia de proveedor sin reiniciar el backend.
4. Usa **Detectar aplicaciones instaladas** o registra accesos manualmente.
5. Autoriza carpetas en **Lectura de archivos** y actualiza su índice.

## Funciones implementadas

- Chat con Gemini u Ollama; selección de proveedor y modelo.
- Historial persistente en SQLite con ventana de hasta 20 mensajes y 12 000 tokens estimados. **Nueva conversación** también elimina el historial persistente.
- Contador de tokens informados por el proveedor, por mensaje y sesión.
- Respuestas fijas, fecha/hora y comandos locales sin consultar al modelo.
- Apertura de accesos, cierre y minimización de aplicaciones; apagado con confirmación.
- Descubrimiento de accesos del menú Inicio sin eliminar los ya registrados.
- Búsquedas en Google, YouTube y Spotify. YouTube intenta abrir el primer video; Spotify abre resultados de búsqueda.
- Búsqueda de archivos por nombre, tipo y ubicación.
- Creación de carpetas y documentos TXT, CSV, DOCX, XLSX, PPTX y PDF.
- Copia, movimiento y cambio de nombre con confirmación válida por 120 segundos; sin sobrescribir archivos existentes.
- Lectura autorizada de TXT, Markdown, CSV, JSON y DOCX; máximo de 2 MB y 24 000 caracteres por archivo enviados como contexto.
- Memoria explícita permanente. Gemini admite recuperación con embeddings en nube; con Ollama se utilizan coincidencias locales.
- Recordatorios y rutinas locales persistentes.
- Activación por nombre, Vosk para comandos y faster-whisper para conversación.
- Edge TTS, Kokoro, ElevenLabs, Fish Audio y API personalizada; caché de audio y RVC opcional con su entorno externo.
- Avatar GLB con movimientos por estado, bandeja e inicio con Windows.

La búsqueda y organización de archivos se interpretan mediante el modelo seleccionado. Las búsquedas en plataformas se procesan localmente. Ollama no hace locales las voces en nube que mantengas seleccionadas.

## Ejemplos

```text
Recuerda que empiezo a trabajar a las 9.
Recuérdame llamar a Ana a las 18:30.
Programa rutina inicio de trabajo a las 09:00 abre Steam y Discord.
Abre el bloc de notas.
Busca noticias de tecnología en Google.
Pon música tranquila en YouTube.
Busca jazz en Spotify.
Busca archivos PDF en descargas.
Crea una carpeta Proyectos en el escritorio.
Crea un Word llamado Informe en documentos con un resumen de mi proyecto.
Crea un Excel llamado Gastos en documentos con columnas Concepto y Monto.
Copia el archivo "C:\Users\TU_USUARIO\Documents\Informe.docx" a descargas.
```

Las rutinas de ese comando son diarias y usan accesos registrados. Las operaciones de archivos se limitan a Escritorio, Documentos, Descargas, Imágenes, Videos y Música. La lectura tiene su propia lista de carpetas autorizadas.

## Datos, credenciales y avatar

Los datos activos se guardan en `%LOCALAPPDATA%\Asistente Modular`: `config`, `data/asistente.sqlite3`, `memories`, `cache` y `logs`. Las claves se guardan mediante el Administrador de credenciales de Windows; también se admiten las variables de entorno de `config/credentials.py` del backend.

`ASISTENTE_DATA_DIR` cambia la carpeta de datos y `ASISTENTE_VOICE_ROOT` cambia la carpeta de voz: son opciones independientes. Las plantillas están en `config/defaults`. `settings.toml` conserva opciones de diseño; no todas son controles implementados.

Coloca el avatar en `assets/avatars/assistant.glb`. También se acepta `asistente.glb`, que tiene prioridad si existen ambos. Al iniciar o compilar se genera `desktop/public/models/assistant.glb`. Sin GLB se muestra un círculo animado. El renderizador no implementa sincronización labial real.

## Comprobaciones

Desde la raíz:

```powershell
.\backend\.venv\Scripts\python.exe -m pip check
Set-Location desktop
npm.cmd run typecheck
npm.cmd run build
Set-Location ..\backend
.\.venv\Scripts\python.exe -m pytest
```

La compilación genera `desktop/out`; no crea un instalador MSI/EXE. El instalador de desarrollo incluye pytest.

Última comprobación de la integración: TypeScript y compilación correctos; 19 pruebas nuevas aprobadas. La suite completa tuvo 100 pruebas aprobadas y 4 fallos de recuperación de comandos de voz y frases cortas de activación. La instalación desde cero y los modelos externos requieren validación adicional.

## Publicar el código

Sube código, pruebas, documentación, `desktop/package-lock.json`, `backend/pyproject.toml` y el manifiesto de voz. `.gitignore` excluye dependencias, entornos, compilados, datos locales y modelos. No necesitas subir los aproximadamente 932 MB de la instalación local.

Sigue [la guía de GitHub](docs/GITHUB.md). Los recursos externos se descargan por separado y mantienen sus propias licencias.
