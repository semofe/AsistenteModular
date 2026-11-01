# Archivos y cachés

- `src/`: implementación del motor; `tests/`: pruebas.
- `.venv/`: dependencias instaladas, necesarias para ejecutar el motor.
- `%LOCALAPPDATA%/Asistente Modular/config`, `data` y `memories`: datos persistentes. No borrar.
- `%LOCALAPPDATA%/Asistente Modular/cache/tts`: audios reutilizables, limitados a 1 GiB por el gestor. Se pueden vaciar desde Configuración.
- `%LOCALAPPDATA%/Asistente Modular/cache/voice`: grabaciones y archivos de síntesis temporales. Cada petición elimina sus archivos al terminar, también cuando falla la síntesis.
- `ASISTENTE_DATA_DIR` permite sustituir la ubicación de datos anterior.
- `pytest-cache-files-*`, `.pip-cache` y `__pycache__` son residuos regenerables. No contienen modelos ni credenciales. Algunas carpetas antiguas tienen acceso denegado y no se pudieron eliminar en la auditoría.

Pytest tiene desactivado `cacheprovider` para evitar nuevos directorios de caché en el backend. Sus temporales usan la carpeta temporal del sistema. No instalar dependencias ni almacenar modelos dentro de carpetas de pruebas temporales.

La respuesta «Perdón, ¿puedes repetirlo?» es una respuesta local prevista para texto no reconocido. El historial de Configuración permite comparar la transcripción recibida y la respuesta. La caché de voz utiliza texto y ajustes de síntesis para identificar cada audio.
