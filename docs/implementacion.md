# Estado de implementación

El inventario vigente de funcionalidades está en [README](../README.md). La instalación y publicación se documentan en [INSTALACION.md](INSTALACION.md) y [GITHUB.md](GITHUB.md).

## Implementado

- Aplicación Electron/Vue, backend FastAPI y comunicación WebSocket.
- Gemini y Ollama, selección de modelos e historial persistente acotado.
- Catálogo de accesos, descubrimiento de aplicaciones y búsquedas en plataformas.
- Búsqueda, generación y organización de archivos con confirmación.
- Lectura autorizada de documentos, memoria explícita, recordatorios y rutinas locales.
- Circuito de voz Vosk/Whisper y síntesis con proveedores configurables.
- Avatar GLB con movimientos generales; conversión RVC mediante un proyecto externo compatible.

## Validaciones y trabajo pendiente

- Validar instalación completa en un Windows limpio y resolver las dependencias transitivas en ese entorno.
- Revisar cuatro pruebas de voz que fallaron en la última suite (100 aprobadas): recuperación de comandos distorsionados y frases cortas de activación.
- Verificar los modelos/servicios externos y documentar una distribución reproducible del proyecto RVC compatible.
- Medir latencia y consumo CPU/GPU/RAM.
- Implementar sincronización labial real, cámara y Piper si se decide incorporarlos.
- Crear empaquetado distribuible y probar la instalación resultante.

No están integradas las herramientas de visión de pantalla ni de consulta de hardware de Mia V5.
