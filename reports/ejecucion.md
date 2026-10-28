# Reporte de pruebas funcionales — BitVerde

## Cambios de UX validados

- Opciones sin cheques ni marcas que anticipen la respuesta. Progreso por etapas, opciones con letras neutrales y feedback textual después de elegir.
- Tres retos cotidianos: laptop/AND, carga del celular/OR y contaminación RAEE, con pistas visibles.
- Reintentos por pregunta sin reiniciar; errores sin premio ni cierre de ronda.
- Finalización idempotente: repetir el envío devuelve el mismo token y no duplica premios.
- Ticket de Circuito tanto por trivia como por registro de RAEE, con copia y nueva partida.
- Lista staff privada de los últimos 10 tokens, polling de 3 segundos y canje con un clic.
- Compatibilidad con tokens anteriores y canje único bajo concurrencia.
- Se conservan las siete categorías oficiales y el punto de recolección de la campaña.

## Ejecución de backend

Entorno: Python 3.11.17, `.venv` local y SQLite dedicada de pruebas en `/tmp/bitverde-tests.db`.

```bash
.venv/bin/python -m pytest -q --junitxml=reports/pytest.xml
```

**Resultado: 24 passed, 1 warning in 3.39s. Código de salida: 0.**

Las 17 pruebas anteriores se adaptaron al nuevo formato de token y a la recuperación del resultado. Se añadieron 7 pruebas que cubren preguntas fáciles y reintentos, validación/expiración por respuesta, finalización concurrente, premio por donación, lista privada de 10 tokens ordenada por emisión y su actualización tras el canje, tokens anteriores y plantillas.

El único aviso es `StarletteDeprecationWarning`: Starlette desaconseja usar `httpx` con `TestClient` y recomienda `httpx2`. No hubo fallos ni pruebas omitidas. La suite se ejecutó fuera del sandbox porque el cliente ASGI se bloquea en ese aislamiento, como se verificó en la ejecución anterior.

## Ejecución JavaScript

Entorno: Node.js v22.23.3, sin dependencias adicionales.

```bash
node tests/test_ui.cjs
```

**Resultado: 3 pruebas aprobadas, 0 fallidas, 0 omitidas.**

- Selección errónea, reintento, selección correcta, progreso, ticket, copia y nueva ronda.
- Ticket compartido y alternativa cuando no hay acceso al portapapeles.
- Lista staff, canje con un clic y actualización del estado.

Estas pruebas ejecutan el JavaScript de la aplicación con un DOM y respuestas HTTP simulados. No validan el renderizado real ni la integración del portapapeles en un navegador.

## Otras comprobaciones

Aprobadas: `node --check app/static/js/app.js`, compilación sintáctica de Python y `git diff --check`.

Evidencias: `pytest.txt`, `pytest.xml`, `ui-tests.txt` y `dependencies.txt`.

## Límites de la validación

La meta de menos de 45 segundos requiere prueba cronometrada con visitantes. No se ejecutó validación visual en navegador, MySQL, Docker en funcionamiento ni DNS/TLS del dominio. La nueva tabla de premios se crea al iniciar; las restricciones de categoría en tablas antiguas siguen requiriendo una migración explícita. No se reclasificaron ni eliminaron registros históricos.
