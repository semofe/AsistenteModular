# Avatar opcional

Coloca el archivo fuente en `assets/avatars/assistant.glb`. También se acepta `asistente.glb`, que tiene prioridad si existen ambos. No se carga automáticamente cualquier otro nombre.

`npm run dev` y `npm run build` copian el modelo a `desktop/public/models/assistant.glb`. Esa copia es generada. Sin modelo se muestra un círculo animado.

El renderizador escala y centra el GLB y genera movimientos generales por estado. No implementa sincronización labial real. Los modelos y sus copias están excluidos de Git; documenta por separado su origen y permiso de uso si los distribuyes.
