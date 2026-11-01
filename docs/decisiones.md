# Decisiones funcionales

- Solo Windows. Hardware de referencia: Ryzen 5 5500, RX 6600 y 24 GB de RAM.
- Electron + Vue + Three.js; motor modular Python.
- Nombre centralizado en `assistant.json` y editable desde Ajustes; la activación usa `Oye {assistant_name}`. El detector local sigue pendiente de validación en español.
- Ocultar avatar a los 120 segundos de inactividad; detener el renderizado y conservar inicialmente el modelo cargado.
- Reiniciar contexto conversacional a los 900 segundos de inactividad, sin resumen ni llamada al modelo. El historial archivado no se reinserta automáticamente. Perfil y recuerdos explícitos permanecen.
- Ambos tiempos editables y calculados desde el fin de la interacción. No vencen durante una petición en curso.
- Sin interrupción hablada: suspender reconocimiento de peticiones durante reproducción y reactivarlo al terminar. Mantener cancelación desde interfaz.
- Gemini 3.6 Flash inicialmente. Ollama opcional desactivado, con URL y nombre de modelo configurables. No cambiar automáticamente a otro proveedor por defecto.
- Sin conexión: aviso local, accesos/rutinas/recordatorios/voz siguen disponibles. Sin Ollama configurado no hay conversación generativa local.
- Personalidad TXT; datos del usuario editables; recuerdos duraderos solo por petición explícita. Guardar historial técnico no equivale a extraer recuerdos automáticamente.
- RAG local sobre documentos seleccionados y recuerdos explícitos. Acceso a una carpeta no autoriza indexarla.
- Permisos separados: listar, abrir, leer, crear, modificar, eliminar y uso de contenido en nube. Validación de rutas resueltas y enlaces antes de cada operación.
- Aplicaciones/juegos registrados por acceso directo, ejecutable o identificador de aplicación. Alias editables y botón Probar. Si falta una app, descubrimiento Windows; solo una coincidencia inequívoca permite registrar y abrir; en otro caso preguntar.
- Cámara bajo petición: enviar imagen a Gemini cuando el uso en nube esté autorizado; no capturar continuamente. Visión offline exige modelo compatible.
- Rutinas por interfaz: pasos ordenados, alias, habilitación, prueba, cancelación y política de fallo. Referenciar accesos por ID estable. Confirmar resultado real.
- Recordatorios y acciones programadas locales, por interfaz o gramática de voz limitada. Ambigüedad exige aclaración; no usar Gemini como fallback automático.
- Notificación, voz o ambas. Los avisos hablados esperan si Asistente Modular está hablando. Aparición por recordatorio configurable.
- Tareas vencidas: mostrar pendientes; preguntar antes de ejecutar aperturas atrasadas. Usar zona horaria Windows y evitar duplicados al reanudar.
- Inicio automático Windows habilitado por defecto en la futura app, desactivable. No configurado por este esqueleto.
- Presupuesto propuesto aceptado: USD 5/mes; avisos 50/80/100%; límite local de nuevas llamadas. No es garantía del importe facturado por el proveedor.
- Entrada habitual 6000 tokens, incluyendo hasta 1000 de RAG. Hasta 3 llamadas al modelo por petición. Salida breve; contabilizar razonamiento, herramientas y reintentos.
- Precios y contadores reales del proveedor se integrarán antes de activar la estimación de costos. No se fijan tarifas históricas en código.

## Arquitectura de ejecución

El router local intenta resolver primero accesos, rutinas y recordatorios. Solo peticiones abiertas requieren Gemini. Los documentos recuperados son datos, nunca autorización para ejecutar acciones.

Electron inicia y supervisa Python; la API escucha solo en loopback, usa un secreto efímero y valida origen y mensajes. Las claves de Gemini permanecen en Python y el almacén Windows. El renderer no recibe acceso general al sistema ni ejecuta comandos arbitrarios.

Estados principales: espera, escucha, procesamiento, respuesta hablada. Visibilidad y sesión son estados separados; ocultarse no reinicia la conversación. No lanzar consultas periódicas al LLM mientras se espera.

La caché de audio identifica texto, motor, voz, versión y ajustes. Una confirmación cacheada nunca sustituye la comprobación de una acción. RVC entrega audio final al reproductor y al controlador de sincronización labial.
