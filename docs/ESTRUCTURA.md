# Organización del proyecto

## Backend

`src/asistente/api/server.py` construye los servicios y gestiona su ciclo de vida. `api/routes.py` compone los routers y mantiene el cambio de proveedor. Los endpoints viven en `api/routers/`: settings, access, conversation, files, schedule, memory y voice. Los modelos de petición HTTP están en `api/http_schemas.py`; `api/schemas.py` conserva los mensajes WebSocket. `api/voice_helpers.py` contiene las funciones de vocabulario y activación, reexportadas desde routes para compatibilidad.

`core/orchestrator.py` dirige la conversación. `memory/` contiene recuerdos, historial, embeddings e indexación en segundo plano. `tools/` implementa las acciones locales, `automation/scheduler.py` la agenda, `providers/` los proveedores de conversación y `storage/` SQLite y sus migraciones.

`src/asistente/voice/` es código fuente necesario. La carpeta `/voice/` de la raíz contiene modelos y entornos externos y se excluye de Git. La regla de exclusión debe permanecer anclada a la raíz para no ocultar los módulos Python.

## Interfaz

`desktop/src/App.vue` coordina la aplicación y conserva la lógica de voz, accesos y configuración. `components/chat/ConversationList.vue` presenta mensajes; `components/memory/MemoryPanel.vue` y `components/schedule/SchedulePanel.vue` presentan formularios y emiten acciones.

`composables/useMemory.ts` y `useSchedule.ts` gestionan estado y operaciones de cada función. Se crean por instancia; no comparten estado global. `types/chat.ts` define los mensajes de presentación. `styles/app.css` conserva los estilos globales. El cliente HTTP/WebSocket sigue en `services/backend.ts`.

## Trabajo pendiente y módulos retirados

Se retiraron 21 módulos Python que solo contenían un docstring de pendiente de implementación, y dos archivos Electron con un comentario equivalente. No se retiraron implementaciones activas.

- `api/auth.py`: no existía implementación de autenticación.
- `automation/executor.py`, `reminders.py`, `routines.py`: la funcionalidad activa permanece en scheduler y orchestrator.
- `context/builder.py`, `session_manager.py`, `sliding_window.py`, `token_budget.py`: el contexto y los límites activos permanecen en orchestrator y conversation_store.
- `core/events.py`, `state_machine.py`: no existían implementaciones independientes.
- `memory/ingestion.py`, `profile.py`, `retrieval.py`: el RAG de recuerdos permanece en explicit_memory; la ingesta documental sigue pendiente.
- `tools/camera.py`: cámara pendiente.
- `voice/audio_input.py`, `audio_output.py`, `vad.py`, `wake_word.py`, `conversion/base.py`, `stt/base.py`, `tts/piper.py`: no contenían implementaciones. La captura y activación activas permanecen en la interfaz; los motores implementados permanecen en voice.
- `desktop/electron/windows.ts`, `autostart.ts`: no contenían implementación; la ventana activa se crea desde main.ts.

No eliminar `voice/worker.py`: se ejecuta como subproceso desde VoiceManager y por eso no aparece como importación normal.

## Próximas mejoras independientes

Extraer configuración, accesos y control de voz de App.vue por etapas. Dividir services/backend.ts por función. Centralizar carpetas conocidas de Windows y confirmaciones, conservando las políticas particulares de lectura y escritura. Resolver los cuatro fallos de pruebas de voz existentes antes de esta reorganización.

## Validación de esta reorganización

- Suite Python: 106 correctas y los mismos 4 fallos de voz ya identificados antes de los cambios.
- Los 44 manejadores HTTP conservan su AST original.
- Los 44 pares método/ruta coinciden con el contrato previo y OpenAPI se genera correctamente.
- TypeScript: correcto. Compilación Electron/Vue: correcta.
- No se probaron manualmente micrófono, reproducción de voz ni servicios externos.
