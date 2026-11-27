# Historia de OPERATIONS.md (incidentes, mediciones y cronología)

Pasajes movidos tal cual de [OPERATIONS.md](../OPERATIONS.md) el 27/11/2026: casos reales, mediciones fechadas y cronología por issue. La regla o el contrato que dejó cada uno vive en OPERATIONS.md.

## Grabador FBCYL: fiabilidad (#446, 23/11/2026)

- el sábado 21/11 el partido de las 17:00 no se grabó. **Causa real (hallada el 23/11): el grabador pedía todo con `requests.get(url)` sin cabeceras y los servidores de FBCYL (el calendario del ESB, las estadísticas y el streaming) cierran la conexión sin responder al agente por defecto de `requests`**: con un `User-Agent` normal responden 200 (medido en los cuatro endpoints). El planificador devolvía «sin partidos» sin dejar rastro y el grabador tampoco habría podido leer nada; `http_get` envía ahora un `Mozilla/5.0` llano. Además, el cron de GitHub tampoco disparó entre las 14:22 y las 20:38 UTC. No hay que depender de lanzarlo a mano.

## Atlas retirado (#724)

- El workflow de comparación (*Atlas compare*) cumplió su función —la última ejecución, en verde, dio el archivo con todo lo que tenía Atlas: 77 colecciones y 2.309 partidos— y se retiró con sus módulos y tests;

## Catálogo de competiciones: alta en un solo sitio y alcance en Atlas (#724, #456)

- ; antes eran cuatro ficheros que se desincronizaban
- y de 3ª FEB solo el grupo A-B en Atlas (el plan gratuito de 512 MB no admite sus 10 subgrupos: ≈ 3.370 partidos/temporada ≈ 0,13 MB cada uno en disco, medido en LF Challenge; 3ª FEB son 1.768).
- **Sin ese límite** (archivo y base local):

## Refresco de fuentes externas: carrera del push (#1068)

- como el de FIBA que terminó en 2 minutos mientras NCAA llevaba 34,

## Fuente FIBA: activación escalonada (#887)

- el 18/11/2026 se activó primero `fiba-u18-eurobasket-2025`, 56 partidos, como comprobación de la cadena real —workflow, Mongo efímero, clave del archivo externo, `git push` y `web-data-ext`—; después, con el cuadre arreglado, los otros 21: juveniles 2024-2026 y los absolutos de 2025,

## Fuente NCAA: primer lote real (#888, 23/11/2026)

- **Medido en el primer lote (23/11/2026, 2.000 peticiones, 34 minutos: ≈ 1 petición por segundo)**: 1.821 partidos nuevos (10 conferencias masculinas, por el orden del catálogo), **≈ 9,8 KB comprimidos por partido** (17,9 MB), **98 no fiables (5,4 %)** —en la ACC, 16 de 371: 2 sin jugada a jugada y el resto con diferencias sueltas, sobre todo triples intentados—, `partial: true` y `last_ok` sin mover, como estaba previsto; el primero salió en rojo por la carrera del push (#1068, corregida). **Una temporada son ≈ 108 MB comprimidos: con 10 temporadas serían ≈ 1,1 GB, así que #967 (los ficheros pesados como assets de release) pasa a ser necesario antes de cargar más de una o dos temporadas de NCAA.**

## NCAA: respuesta cortada (#1088, 24/11/2026)

- el segundo intento del lote murió tras ~20 minutos con `IncompleteRead(645685 bytes read)`:

## NCAA: un partido ilegible tumbaba la ejecución (#1086, 24/11/2026)

- el lote del 24/11 falló con `NcaaPageError: the game is not in the expected format (KeyError: 'id')` porque la fuente fallaba al final del recorrido de **cada entrada** si todos los partidos nuevos de esa entrada eran ilegibles (una conferencia con uno solo, malformado, tumbaba todas las siguientes y la fecha de arranque no avanzaba). Ahora `NcaaSource.finish()`

## NCAA: coste de la publicación y qué se hizo (#888, 23/11/2026)

- el `Web data ext` del primer lote (1.821 partidos) llevaba más de 90 minutos. Perfilado con partidos reales de NCAA (la ACC, con `mongomock`: valen el reparto y el crecimiento, no los tiempos absolutos), **`inout` y `lineups` eran el 84 % del tiempo** y las filas el 6 %. (1) **`inout` era cuadrático**: por cada jugador se recorrían todos los partidos de la colección y se reanalizaba la jugada a jugada de los de su equipo (10 partidos: 18 s; 30: 134 s); ahora

## Histórico: decisión de publicación del 19/11/2026 (#991)

- Motivo: con las tandas 1 y 2 cargadas `web-data` pesaba 209 MB (la estimación de las cuatro tandas era 84 + 60–190 MB).
- , que sustituye a la del 13/11** (el detalle completo de todas las temporadas antiguas en `web-data`)

## Tandas del histórico: tanda 1 (#876)

- ; el refresco que la cargó, el 16/11, tardó ≈ 80 min y quedó en rojo por 404 de partidos sin caja; los siguientes, 6-7 min

## Colecciones cerradas: medición tras #924 (13/11/2026)

- **Medido el 13/11/2026 con #924 en `main`**: el primer refresco (comprueba todo, deja el estado guardado) 17 min, con el scrape en 13 min (antes 25 y 23); el segundo, **5 min 14 s en total y 1,5 min de scrape: 304 de 366 colecciones cerradas y 62 comprobadas**, 0 partidos nuevos. Lo que queda es **restaurar y guardar el archivo (43 s + 2,3 min, el 57 % del run)**, que crece con su tamaño (111,9 MB hoy): las temporadas anteriores a la actual y la previa se archivan «ligeras», sin jugada a jugada.

## DERIVED: el refresco local no lo rellenaba (#630)

- : el local no lo hacía y dejó 167 partidos fuera de «Análisis pbp»

## Archive refresh: partido en juego 2537218, Atlas, incomparecencias (#724, #902, #950)

- Sin esto, el partido 2537218 de 3ª FEB B-B (jugado el 11-10-2026, aún «SCHEDULED» con los cuatro cuartos en FEB) se saltaba en cada refresco y dejaba el run en rojo siempre, ocultando los fallos de verdad (con el refresco de Atlas no se veía porque solo cubría el grupo A-B).
- *Archive refresh* corre en paralelo al *Atlas refresh* hasta que éste se retire; `web-data` espera ahora a *Archive refresh* y `live-packages` sigue esperando al de Atlas hasta el paso 4 de #724.
- ; son los dos del CE SSAA Cadete Fem. 2025/26 que mantuvieron en rojo el primer refresco programado tras #902
- ; hasta entonces ninguno tenía fecha y solo se perdonaban las incomparecencias: con la tanda del histórico, cuatro partidos de 2022-23 y 2023-24 sin boxscore en FEB dejaban rojo cada refresco

## Archive refresh: límite de tiempo (#1067, 23/11/2026)

- , así que un scrape que gastaba todo el tiempo perdía todo lo descargado, y una carga siempre mayor que el límite habría fallado para siempre. Ahora

## Coste del refresco: medición del 13/11/2026 (#924)

- **Medido el 13/11/2026** (run a mano de 25 min, línea de tiempo del runner con las marcas de Mongo): restaurar el archivo 23 s · **fase FEB 20 min para 327 colecciones sin ningún partido nuevo (≈ 3,7 s por colección)** · fase FBCYL 2,9 min para 37 grupos y 368 partidos nuevos (≈ 0,5 s por partido) · guardar el archivo 80 s. Hasta el 11/11 (≈ 85 colecciones activas) un refresco normal tardaba 3–7 min; desde el 12/11 (≈ 330, con el histórico de 2024 y 2025) 25–29:

## Partidos que fallan: umbrales anteriores (#1021)

- (20 y 7 hasta #1021: las tandas del histórico dejaban el run en rojo una semana)

## web-data: alta y baja (#1082) y tiempo de construcción (#944)

- **Medido el 25/11/2026** (tiempo de «Build the artifacts» en runs limpios de Web data): 1.430–1.686 s antes de la baja y 1.944–1.974 s leyéndolas en cada publicación (+4 a +9 minutos, +20 a +35 %), de ahí el cambio; el
- , el 16/11/2026 un cambio de `src/live_core` recalculó `lineups` e `inout` en las 366 competiciones y a los 120 min de entonces solo llegó a 352 —63 min de combinaciones y 36 de IN/OUT—, así que no publicó y cada refresco siguiente habría vuelto a empezar

## Live packages: guarda de fases, el caso real (#724)

- Pasó de verdad: el primer refresco que sembró los metadatos en el archivo fue uno parcial (`only: tercera feb`) y los paquetes salieron con 3 rivales y las rondas de una sola competición en vez de 12 y las de ocho.

## Protocolo de despliegue: casos reales (#789, 06/11/2026)

- : el 06/11/2026 el *Web data* falló en LF Endesa por una jugada sin equipo que la base local no tenía, y paró la publicación de todo
- antes un run rojo empujaba los ficheros que había calculado hasta fallar y los dejaba huérfanos en la rama;

## Dependencias: estado del 23/10/2026 (#526)

- Estado del 23/10/2026: la app live sin avisos; el frontend sin avisos (0 vulnerabilidades) tras subir `jspdf` (crítico), `axios`, `dompurify`, `lodash`, `form-data` y `react-router-dom` a la 7 (#526).

## Memoria: workers por defecto (#163)

- Antes `run_api.py` lanzaba 4 en Linux → ~500-700 MB en reposo y OOM intermitente al desplegar.

## Google Play: el keystore se creyó perdido (11/11/2026)

- (el 11/11/2026 se creyó perdido: estaba solo en un Drive)

# Servidor de la API, clave de administración y memoria del servidor (retirados en #1199, 27/11/2026)
Lo que decía `docs/OPERATIONS.md` antes de eliminar la API, tal cual estaba (el estado actual está en OPERATIONS.md, «Sin servidor de API»).

### Estado actual: servidor sin escrituras y ADMIN_API_KEY sin uso (#724)
- **El servidor ya no recibe escrituras de la web (#724).**
  - Se retiraron la página Administración, `DELETE /collections/{name}`, `POST /scrape/*`, `POST /historical/ingest*` y el servicio `basketlab-scraper`.
  - **Cargar datos** es el refresco programado del archivo (*Archive refresh*, abajo) y **retirar una competición** es la purga (*Archive purge*).
- `ADMIN_API_KEY` **no está definida en producción**, a propósito, y **ninguna ruta la usa hoy**: el entrenamiento del predictivo antiguo (`/analysis/elasticity/train`) se retiró con él (#853, el análisis predictivo vive ahora en el navegador y no escribe nada en el servidor).
- La guarda (`require_admin`, `src/api/security.py`) se conserva como patrón para la próxima ruta de escritura y se prueba sobre una aplicación pequeña (`tests/test_admin_auth.py`); `tests/test_server_writes_retired.py` exige que no quede ninguna ruta que la pida.
- En producción (`ENVIRONMENT=production`; este repositorio no aloja ninguna API, ver *Sin servidor alojado*) todas las lecturas y el cómputo sin persistir (informe de equipo, export PDF, informe semanal) funcionan; una ruta de escritura futura con la guarda respondería **503** («ADMIN_API_KEY no está configurada en el servidor») hasta que se defina la clave, y en **local** (sin `ENVIRONMENT=production`) estaría abierta.

Para cargar o refrescar datos en local: `python run_archive.py pull` + `load` sobre un Mongo local y `python run_refresh.py --config config/competitions.json` contra él (ver *Refrescar el archivo sin Atlas*); ya no hay página ni ruta de servidor para ello.

### Sin servidor alojado: la API solo sirve para desarrollo, pruebas y e2e (#334)
- **BasketLab no depende de ninguna plataforma de alojamiento de la API ni se integra con ella** (Render se retiró del proyecto el 05/11/2026): no hay `render.yaml`, ni job de despliegue en CI, ni comprobación posterior, y `GET /api/v1/health` informa del commit solo si el entorno define `GIT_COMMIT`.
- La web publicada lee los ficheros de `web-data` (el valor por defecto desde #745) y la API (`python run_api.py`) **se conserva a propósito para desarrollo local, pruebas y el e2e** (decisión del 05/11/2026; eliminarla es una decisión aparte: el rework del predictivo, #641, se resolvió sin ella en #841).
- Quien aloje la API necesita las variables de abajo y `VITE_API_BASE` en la web para que su respaldo la use.
- **Fuera del repositorio** (a mano, GitHub → *Settings → Secrets and variables → Actions*): borrar la variable `RENDER_API_URL` si existe (nada la lee ya) y, si alguna vez se definieron, los secretos `RENDER_DEPLOY_HOOK_URL` y `RENDER_SCRAPER_DEPLOY_HOOK_URL` (a 05/11/2026 no hay ninguno).

### Clave de administración ADMIN_API_KEY: activar, rotar y diagnosticar

### Activar la clave (paso a paso)
Hoy ninguna ruta la usa. Hacerlo cuando exista una ruta de escritura con `Depends(require_admin)` y se quiera usarla en producción.

1. **Generar una clave larga y aleatoria** (en cualquier terminal; no la pegues en el chat ni la commitees):
   - PowerShell: `[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))`
   - o Python: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   Guárdala en un gestor de contraseñas.
2. **Entorno del servidor de la API**: añadir `ADMIN_API_KEY` = la clave.
3. (El servicio `basketlab-scraper` se retiró en #724: solo la API tiene la clave; el frontend la envía en `X-Admin-Key`.)
4. **Reiniciar** el servicio para que lea la variable.
5. **Introducir la clave en la app**: la web ya no tiene ningún campo para ella (la página Admin se retiró en #724 y el entrenamiento del predictivo en #852); por `curl` basta la cabecera `X-Admin-Key`.
6. **Comprobar** con la ruta nueva: sin la cabecera `X-Admin-Key` responde **401**; con la clave correcta pasa la guarda (cualquier otro código, pero ya no 401 ni 503). Usa una petición que no destruya nada al probar.

### Rotar o retirar la clave
- **Rotar**: cambiar el valor en el entorno del servidor, reiniciar y volver a guardarla donde se use. Las claves antiguas dejan de valer al instante (se lee en cada petición).
- **Retirar** (volver al estado actual): borrar la variable y reiniciar → las rutas con guarda vuelven a responder 503.

### Diagnóstico: 401, 503 y CORS (tabla de síntomas)
| Síntoma | Causa | Solución |
|---|---|---|
| 503 "ADMIN_API_KEY no está configurada" | variable sin definir en ese servicio (producción) | Estado actual esperado; pasos de arriba para activarla |
| 401 "Clave de administración requerida o incorrecta" | sin la cabecera `X-Admin-Key` o clave distinta | Enviar la clave correcta |
| 503 "Base de datos no disponible: …" (o 500 en versiones antiguas) en cualquier endpoint con datos | `MONGODB_CONNECTION_STRING` sin definir, credenciales de Atlas rechazadas, usuario sin permisos o IP no permitida | Abrir `/api/v1/health/db` (detalle debajo de la tabla) |
| CORS / `OPTIONS` bloqueado | `ALLOWED_ORIGINS` no incluye la URL de Vercel | Ajustar `ALLOWED_ORIGINS` (la cabecera `X-Admin-Key` está permitida) |
| Funciona en local pero no en producción | en local no hay guarda (sin `ENVIRONMENT=production`) | Esperado |

Base de datos no disponible (503 «Base de datos no disponible: …»):
- Abrir `/api/v1/health/db`: `error` = `missing_config` / `auth_failed` / `not_authorized` / `unreachable` / `invalid_config` y `hint`.
- Revisar las variables de entorno del servicio y Atlas → Database Access / Network Access (`0.0.0.0/0` para Render free).


### Memoria (servidor pequeño, 512 MB)
Un documento de partido pesa ≈ 1 MB en memoria de Python y la app completa ≈ 170 MB en reposo (más: matplotlib +45, pandas +50). Medidas tomadas (issue #163), vigentes si alguien aloja la API en un servidor con poca RAM:
- **Un solo worker** de uvicorn por defecto (`src/api/runtime.uvicorn_workers`; `WEB_CONCURRENCY` lo sube, tope 4).
- `MALLOC_ARENA_MAX=2` (menos fragmentación) y `pip install --no-cache-dir` al instalar.
- Listado de partidos con **proyección** (no cargar documentos completos), zonas de liga **en streaming** y caducidad (15 min) de los ZIP del informe semanal sin descargar.
- **Diagnóstico**: poner `LOG_MEMORY=1` en el servicio; los logs mostrarán `WARNING basketlab.memory GET /ruta rss 412 MB (+90 MB)` para peticiones que suben ≥ 25 MB (`LOG_MEMORY_DELTA_MB`) o dejan el RSS ≥ 350 MB (`LOG_MEMORY_HIGH_MB`).
- Regla de código: nunca `find({})` sin proyección sobre colecciones de partidos; iterar cursores/generadores en vez de materializar listas de documentos o tiros.
Si aun así se supera el límite: más memoria.

