[CmdletBinding()]
param(
  [switch]$SkipVoiceRuntime,
  [string]$PythonExecutable = 'python',
  [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $repoRoot 'backend'
$desktopRoot = Join-Path $repoRoot 'desktop'
# Misma ruta predeterminada que VoiceManager; no exige que exista al clonar.
$defaultVoiceRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot '..\AsistenteModularData\voice'))
$voiceRoot = if ($env:ASISTENTE_VOICE_ROOT) { [IO.Path]::GetFullPath($env:ASISTENTE_VOICE_ROOT) } else { $defaultVoiceRoot }
$python = (Get-Command $PythonExecutable -ErrorAction Stop).Source
$node = (Get-Command node -ErrorAction Stop).Source
$npm = (Get-Command npm.cmd -ErrorAction Stop).Source

function Invoke-Checked {
  param([string]$Executable, [string[]]$CommandArgs)
  & $Executable @CommandArgs
  if ($LASTEXITCODE -ne 0) {
    throw "El comando fallo con codigo ${LASTEXITCODE}: $Executable $($CommandArgs -join ' ')"
  }
}

Invoke-Checked $python @('-c', "import sys; assert (3,11) <= sys.version_info < (3,13), 'Usa Python 3.11 o 3.12 (64 bits)'; assert sys.maxsize > 2**32, 'Usa Python de 64 bits'; print('Python:', sys.version.split()[0])")
Invoke-Checked $node @('-e', "const [a,b]=process.versions.node.split('.').map(Number); if (!((a===20&&b>=19)||(a===22&&b>=12)||a>22)) { console.error('Se requiere Node 20.19+ o 22.12+'); process.exit(1); } console.log('Node:', process.versions.node)")
Write-Host "Proyecto: $repoRoot"
Write-Host "Entorno de voz: $voiceRoot"
if ($CheckOnly) {
  Write-Host 'Requisitos basicos correctos. No se han instalado paquetes.'
  return
}

$backendPython = Join-Path $backendRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $backendPython)) {
  Invoke-Checked $python @('-m', 'venv', (Join-Path $backendRoot '.venv'))
}
Invoke-Checked $backendPython @('-c', "import sys; assert (3,11) <= sys.version_info < (3,13), 'El entorno backend existente usa una version de Python incompatible'")
Invoke-Checked $backendPython @('-m', 'pip', 'install', '--upgrade', 'pip')
# Reconocimiento y Kokoro se instalan en el trabajador separado, sin duplicarlos.
Invoke-Checked $backendPython @('-m', 'pip', 'install', '-e', "${backendRoot}[dev]")

Push-Location $desktopRoot
try {
  Invoke-Checked $npm @('ci')
  Invoke-Checked $npm @('run', 'sync-avatar')
} finally {
  Pop-Location
}

if (-not $SkipVoiceRuntime) {
  $voicePython = Join-Path $voiceRoot '.venv-voice\Scripts\python.exe'
  if (-not (Test-Path -LiteralPath $voicePython)) {
    New-Item -ItemType Directory -Force -Path $voiceRoot | Out-Null
    Invoke-Checked $python @('-m', 'venv', (Join-Path $voiceRoot '.venv-voice'))
  }
  Invoke-Checked $voicePython @('-c', "import sys; assert (3,11) <= sys.version_info < (3,13), 'El entorno de voz existente usa una version de Python incompatible'")
  Invoke-Checked $voicePython @('-m', 'pip', 'install', '--upgrade', 'pip')
  Invoke-Checked $voicePython @('-m', 'pip', 'install', '-r', (Join-Path $backendRoot 'requirements-voice-worker.txt'))
  if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -and -not $env:ASISTENTE_FFMPEG_PATH) {
    Write-Warning 'Falta FFmpeg para preparar audio de Vosk/RVC. Consulta docs/INSTALACION.md.'
  }
  if (-not (Test-Path -LiteralPath 'C:\Program Files\eSpeak NG\libespeak-ng.dll')) {
    Write-Warning 'Kokoro requiere eSpeak NG de 64 bits en C:\Program Files\eSpeak NG.'
  }
  Write-Host 'Los modelos Vosk/Kokoro y el proyecto RVC se configuran por separado: docs/INSTALACION.md.'
}
Write-Host 'Instalacion terminada. Desde la raiz ejecuta: cd desktop'
Write-Host 'Luego: npm.cmd run dev'
