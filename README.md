# BitVerde

Quiosco RAEE con FastAPI, SQLAlchemy 2, MySQL 8 y SQLite. HTML semántico, Tailwind vía CDN, CSS adaptable y JavaScript sin herramientas de compilación. QR generado en el servidor, sin enviar datos a terceros.

## Desarrollo local (Python 3.11+)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# Edita .env y define STAFF_PASSWORD antes de usar /staff.
uvicorn app.main:app --reload
```

Abre `http://localhost:8000`. SQLite crea `bitverde.db` al iniciar. Si pruebas el QR con un teléfono, configura `PUBLIC_URL` con la dirección accesible desde el teléfono y arranca con `--host 0.0.0.0`. El valor predeterminado del QR es el dominio de producción solicitado.

| Ruta | Uso |
| --- | --- |
| `/` | Trivia móvil de tres preguntas |
| `/registro` | Registro y comprobante imprimible |
| `/dashboard` | Dos stands alineados, métricas y un QR para cada proyecto |
| `/staff` | Consulta y canje, protegido por HTTP Basic |
| `/docs` | API OpenAPI interactiva |
| `/health` | Comprobación de aplicación y base de datos |

## Funcionamiento

La trivia presenta tres retos cotidianos: encender una laptop (AND), cargar un celular (OR) y evitar contaminar con RAEE. Incluye pistas visibles y botones grandes. Las opciones se mezclan al iniciar cada ronda y el servidor conserva ese orden para validar las respuestas. Está diseñada con el objetivo de completarse en menos de **45 segundos**, sin cuenta regresiva ni conocimientos previos. Este objetivo necesita validación cronometrada con visitantes; las pruebas automatizadas no miden el tiempo de lectura.

Cada opción se comprueba en el servidor mediante `POST /api/trivia/{session_id}/answer`. Un error permite reintentar la misma pregunta sin perder el avance. El acierto muestra un borde verde y avanza tras 450 ms. Los estados incluyen mensajes de texto y atributos accesibles; la vibración visual suave se omite cuando el visitante solicita reducir el movimiento.

La ronda caduca a los 20 minutos. `POST /api/trivia/{session_id}/submit` vuelve a validar las tres respuestas: un intento incorrecto no cierra la ronda. Al acertar las tres, emite un único token hexadecimal de 64 bits con prefijo `#BIT-`, por ejemplo `#BIT-A4F29C315D627E80`. Repetir el envío final recupera el mismo token, incluso si se perdió la respuesta de red; no incrementa el contador ni emite otro premio. Los tokens conservan longitud suficiente para el stand y no requieren transcripción gracias al panel staff.

Tanto una trivia completada como una donación registrada muestran el **Ticket de Circuito** con “¡Reto completado! Muestra este token al staff para recibir tu bocadillo.”, el token destacado y botones para copiarlo y jugar de nuevo. Si el portapapeles no está disponible, se ofrece seleccionar el código o guardar una captura. El último token se conserva en el almacenamiento local del navegador y se recupera al volver al juego, incluso después de cerrar la pestaña. El staff comprueba si ya fue canjeado. Este guardado no consulta ni actualiza el estado del canje; en dispositivos compartidos se verá el último ticket. Cada donación registra su premio en la misma transacción que el comprobante; no incrementa la métrica de trivias completadas.

`GET /api/staff/tokens`, protegido con HTTP Basic, devuelve los últimos **10 tokens** de trivia y donaciones por fecha de emisión. `/staff` actualiza la lista cada **3 segundos** y permite **Marcar Canjeado** con un toque; conserva también la búsqueda manual. Una actualización condicional garantiza un solo canje incluso ante solicitudes concurrentes. Canjes repetidos devuelven HTTP 409. Los tokens anteriores con formato `#0x…-BIT` siguen siendo consultables, visibles en la lista y canjeables. Ningún token de premio se publica en el dashboard.

Las tablas `rewards` y `donation_requests` se crean automáticamente al iniciar, sin alterar tablas existentes. El sistema limita a un premio por ronda o registro; no identifica personas ni impide que una misma persona complete varias rondas o registre varias entregas.

Punto de recolección oficial: **Facultad de tecnología e innovación (Edificio A)**. Se publica en los metadatos HTML y en todas las vistas.

Categorías oficiales (compartidas entre formulario, validación API y restricción de base de datos): Celulares, Cargadores, Cables, Teclados, Mouse, Audífonos y Otros aparatos en desuso.

El registro recibe alias, categoría, cantidad entera y peso estimado con hasta tres decimales; 0 kg significa aún no pesado. Guarda un identificador aleatorio y el JSON canónico codificado en UTF-8, representado en hexadecimal y binario (educativo, no una lectura física del circuito). El comprobante se muestra inmediatamente y permite imprimir o guardar como PDF desde el navegador. No hay una consulta pública posterior del comprobante con datos personales. El formulario guarda el intento pendiente en sessionStorage y envía una cabecera `Idempotency-Key`. Ante una interrupción de red, reintentar o recargar esa pestaña recupera el mismo comprobante y premio. Mientras está pendiente, sus campos quedan bloqueados para conservar los datos originales. Una nueva entrega desde el enlace del comprobante recibe otra clave. La API conserva compatibilidad con clientes sin cabecera; esos clientes no tienen esta protección. Si el navegador bloquea el almacenamiento o no dispone de generación criptográfica de claves, no se envía el registro. Se usa `crypto.randomUUID()` cuando está disponible y `crypto.getRandomValues()` como alternativa para acceso local por HTTP.

El dashboard publica solo agregados e IDs de donaciones; nunca alias ni tokens de premio. No convierte kilos recogidos en estimaciones de CO₂ sin una metodología validada.

El panel Eco-Tech incrusta directamente `https://eco-tech-w2cv.onrender.com/estadisticas` mediante un iframe. Conserva el contenido y los estilos de la página oficial y la vuelve a cargar cada 30 segundos para consultar resultados nuevos. El enlace «Abrir estadísticas» permite abrir la fuente en otra pestaña.

En escritorio (más de 900 px), los encabezados, las zonas de datos y los QR comparten filas y aprovechan el alto de la pantalla. Las últimas entregas de BitVerde rotan por grupos para evitar scroll interno. La página oficial de Eco-Tech conserva su propio desplazamiento cuando su contenido supera el área disponible; al ser de otro dominio, BitVerde no modifica su diseño interno. En móvil se conserva el desplazamiento vertical natural. El QR de Eco-Tech abre su página principal y el de BitVerde mantiene `PUBLIC_URL`.

HTTP Basic usa comparación de credenciales en tiempo constante. Sin contraseña configurada, staff permanece cerrado. Usa HTTPS en producción; no guardes contraseñas en el frontend. Los POST rechazan orígenes distintos cuando el navegador envía `Origin`. El despliegue de un evento público de gran tráfico requiere añadir límites de solicitudes en infraestructura; no se incluye control de identidad de participantes ni protección distribuida contra abuso.

## Docker, MySQL y Caddy

1. Copia `.env.example` a `.env`. Define contraseñas distintas para `STAFF_PASSWORD` (mínimo 16 caracteres), `MYSQL_PASSWORD` y `MYSQL_ROOT_PASSWORD`. Para MySQL utiliza valores seguros para URL, por ejemplo generados con `openssl rand -hex 24`. Define `ACME_EMAIL` con un correo real.
2. Apunta DNS A (y AAAA solo si IPv6 funciona) de `bitverde.jaimeberrios.com` al servidor. Abre TCP 80/443 y UDP 443 para HTTP/3.
3. Ejecuta:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 app caddy
```

Caddy gestiona certificados y redirige HTTP a HTTPS. Solo Caddy publica puertos; MySQL y FastAPI quedan en redes Docker. `--forwarded-allow-ips=*` se usa exclusivamente porque la app no publica un puerto al host; si cambias la topología, restringe la confianza al proxy. Si ya existe Caddy en el servidor, integra `reverse_proxy` en él y evita iniciar un segundo servicio en los mismos puertos.

Los volúmenes `mysql_data`, `caddy_data` y `caddy_config` preservan información y certificados. No uses `docker compose down -v` si deseas conservar los registros. Respalda MySQL con `mysqldump` desde una sesión segura y prueba la restauración antes del evento. Las credenciales iniciales de MySQL solo se aplican a un volumen vacío; cambiarlas en `.env` no rota usuarios existentes.

Las tablas se crean al primer arranque con `create_all`. Esta versión inicial no incluye migraciones: un cambio posterior de esquema requiere una migración explícita (por ejemplo, Alembic), además de respaldo.

## Pruebas

```bash
python -m pytest -q
node --check app/static/js/app.js
node tests/test_ui.cjs
```

Las pruebas usan una base SQLite dedicada en `/tmp/bitverde-tests.db` y la reinician. Cubren reintentos, respuestas cotidianas, recuperación de premios, categorías oficiales, expiración, validación, privacidad del dashboard, bytes UTF-8, autenticación, lista staff, tokens antiguos y envíos/canjes concurrentes. Las pruebas JavaScript usan el ejecutor integrado de Node y un DOM simulado para verificar selección, progreso, ticket, portapapeles y canje con un clic; no sustituyen la validación visual en navegador. No ejecutes varias suites a la vez contra ese mismo archivo.

Comprobación manual antes del evento: probar móvil y monitor, escanear QR físico, registrar una entrega, guardar comprobante y canjear un token dos veces. MySQL/Docker, DNS y emisión TLS necesitan validación en el servidor de destino.

## Organización

`app/core`: configuración, conexión y seguridad. `models`: persistencia. `schemas`: validación. `services`: banco de preguntas. `routes/api.py`: operaciones JSON; `routes/views.py`: vistas Jinja. `static`: estilos y comportamiento. Tailwind usa CDN y las fuentes usan Google Fonts con alternativas locales. El CSS local define la presentación principal; la lógica y el QR funcionan sin esos servicios. Para eliminar dependencias externas, compila Tailwind y sirve fuentes locales antes del despliegue.

Referencias técnicas: [HTTP Basic en FastAPI](https://fastapi.tiangolo.com/advanced/security/http-basic-auth/), [SQLAlchemy y MySQL](https://docs.sqlalchemy.org/en/20/dialects/mysql.html), [SQLAlchemy y SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html).

Si existe una base de datos creada con las categorías anteriores, respáldala y migra los valores antes de aplicar la nueva restricción de categoría. `create_all` no altera tablas existentes; no se reclasifican registros históricos automáticamente.

## Recursos institucionales

Las cuatro imágenes proporcionadas se conservan sin modificar en `app/static/images/`. El pie de página compartido muestra `logo-unab.png` y `logo-facultad.png`, con texto alternativo, proporciones originales y carga diferida. `logo-portada.png` y `acreditacion.png` quedan disponibles para futuros usos.
