# Reporte de pruebas funcionales — BitVerde

Contenido actualizado antes de ejecutar la suite:

- Categorías exactas: Celulares, Cargadores, Cables, Teclados, Mouse, Audífonos y Otros aparatos en desuso.
- Catálogo compartido por formulario, Pydantic y modelo SQLAlchemy; restricción CHECK en tablas nuevas.
- Punto de recolección en metadatos HTML y texto visible de todas las vistas: Facultad de tecnología e innovación (Edificio A).

Entorno: Python 3.11.17, entorno virtual local `.venv`, SQLite dedicada de pruebas en `/tmp/bitverde-tests.db`. Dependencias instaladas desde `requirements-dev.txt`; versiones efectivas en `dependencies.txt`. `pip check`: sin dependencias incompatibles.

Comando:

```bash
.venv/bin/python -m pytest -v --junitxml=reports/pytest.xml
```

Resultado: **17 passed, 1 warning in 0.91s**. Código de salida: **0**.

| Cobertura | Pruebas aprobadas |
| --- | ---: |
| Trivia aprobada y canje concurrente único | 1 |
| Trivia fallida, validación y expiración | 1 |
| Bytes UTF-8, métricas y privacidad | 1 |
| Vistas, autenticación, origen y QR | 1 |
| Registro y persistencia de cada categoría oficial | 7 |
| Rechazo de las categorías anteriores | 5 |
| Opciones HTML, OpenAPI, punto de recolección y restricción SQL directa | 1 |

El aviso es `StarletteDeprecationWarning`: Starlette desaconseja usar `httpx` con `TestClient` y recomienda `httpx2`. No hubo fallos ni pruebas omitidas; se conserva el aviso en la salida completa.

La ejecución dentro del sandbox se bloqueó al iniciar el cliente ASGI; se interrumpió y se ejecutó la suite fuera del aislamiento, donde terminó correctamente. La descarga de dependencias también necesitó acceso de red fuera del sandbox.

Comprobaciones adicionales aprobadas: compilación sintáctica Python, `node --check app/static/js/app.js` y `git diff --check`.

Evidencias: `pytest.txt` (salida completa), `pytest.xml` (JUnit) y `dependencies.txt` (versiones instaladas).

Alcance: API y renderizado de plantillas mediante TestClient con SQLite. No se ejecutó validación visual en navegador, MySQL, Docker en funcionamiento ni DNS/TLS del dominio. Las tablas existentes requieren migración explícita para incorporar la nueva restricción; no se modificaron ni reclasificaron registros históricos.
