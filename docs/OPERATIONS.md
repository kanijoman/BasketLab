# Operaciones: despliegue y clave de administración
Léelo cuando toques Render/Vercel, variables de entorno, veas un 401/503 en Admin/scrape/ingesta/entrenamiento, o vayas a compilar/publicar/instalar la app Android. Arquitectura general: [ARCHITECTURE.md](ARCHITECTURE.md).

## Estado actual (decisión consciente)
`ADMIN_API_KEY` **no está definida en producción**, a propósito: la aplicación no es pública y se prefiere que esas rutas queden cerradas. Consecuencia en Render (`ENVIRONMENT=production`):

| Funciona | Responde **503** ("ADMIN_API_KEY no está configurada en el servidor") |
|---|---|
| Todas las lecturas (equipos, jugadores, tiros, informes, rankings, rotaciones…) | `DELETE /api/v1/collections/{name}` (borrar colección) |
| Cómputo sin persistir: informe de equipo, export PDF, informe semanal, Monte Carlo, predicción de partido | `POST /api/v1/scrape/start` (descargar competiciones) |
| | `POST /api/v1/historical/ingest` y `/ingest_competition` |
| | `POST /api/v1/analysis/elasticity/train` y `/train/stream` (entrenar modelos) |

El 503 es el comportamiento diseñado, no un fallo (`src/api/security.py`, probado en `tests/test_admin_auth.py`). En **local** (sin `ENVIRONMENT=production`) esas rutas están abiertas y no hace falta clave.

Para cargar o refrescar datos mientras la clave no exista: ejecutar la API/scraper en local (`python run_api.py`) con `MONGODB_CONNECTION_STRING` apuntando a la misma base de Atlas; en local no hay guarda.

## Activar la clave (paso a paso)
Hacerlo cuando se quiera usar Admin, scrape, ingesta o entrenamiento en producción.

1. **Generar una clave larga y aleatoria** (en cualquier terminal; no la pegues en el chat ni la commitees):
   - PowerShell: `[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))`
   - o Python: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   Guárdala en un gestor de contraseñas.
2. **Render → servicio `basketlab-api` → Environment**: añadir `ADMIN_API_KEY` = la clave. Guardar.
3. **Render → servicio `basketlab-scraper` → Environment**: añadir `ADMIN_API_KEY` con **exactamente el mismo valor** (el scraper tiene su propia guarda: el frontend envía la misma clave a ambos).
4. **Redeploy** de los dos servicios (Render los reinicia al guardar variables; si no, *Manual Deploy → Deploy latest commit*). Los servicios gratuitos tardan en despertar.
5. **Introducir la clave en la app**: página **Admin** → campo "Clave de administración" → *Guardar*. Se guarda solo en esa sesión del navegador (`sessionStorage`); al cerrar la pestaña hay que volver a ponerla.
6. **Comprobar** (sustituye URL y clave):
   ```bash
   # sin clave -> 401
   curl -i -X DELETE https://<api>.onrender.com/api/v1/collections/PRUEBA_INEXISTENTE
   # con clave -> pasa la guarda (404/200 según exista la colección, pero ya no 401/503)
   curl -i -X DELETE -H "X-Admin-Key: <clave>" https://<api>.onrender.com/api/v1/collections/PRUEBA_INEXISTENTE
   ```
   Cuidado: usa un nombre de colección que **no exista** al probar.

## Rotar o retirar la clave
- **Rotar**: cambiar el valor en los dos servicios de Render, redeploy y volver a guardarla en Admin. Las claves antiguas dejan de valer al instante (se lee en cada petición).
- **Retirar** (volver al estado actual): borrar la variable en ambos servicios y redeploy → vuelven los 503.

## Diagnóstico
| Síntoma | Causa | Solución |
|---|---|---|
| 503 "ADMIN_API_KEY no está configurada" | variable sin definir en ese servicio (producción) | Estado actual esperado; pasos de arriba para activarla |
| 401 "Clave de administración requerida o incorrecta" | sin clave en Admin, clave distinta o variable distinta entre `api` y `scraper` | Re-guardar la clave en Admin; comprobar que el valor es idéntico en ambos servicios |
| 503 "Base de datos no disponible: …" (o 500 en versiones antiguas) en cualquier endpoint con datos | `MONGODB_CONNECTION_STRING` sin definir, credenciales de Atlas rechazadas, usuario sin permisos o IP no permitida | Abrir `/api/v1/health/db`: `error` = `missing_config` / `auth_failed` / `not_authorized` / `unreachable` / `invalid_config` y `hint`. Revisar Render → Environment y Atlas → Database Access / Network Access (`0.0.0.0/0` para Render free) |
| Atlas desactualizado respecto a local | el scrape se hizo solo contra la BD local | `GET /api/v1/collections/{name}/freshness` lista `missing_codes` (jugados en FEB y ausentes) |
| CORS / `OPTIONS` bloqueado | `ALLOWED_ORIGINS` no incluye la URL de Vercel | Ajustar `ALLOWED_ORIGINS` (la cabecera `X-Admin-Key` está permitida) |
| Funciona en local pero no en producción | en local no hay guarda (sin `ENVIRONMENT=production`) | Esperado |

## Variables de entorno (resumen)
Backend (Render): `ENVIRONMENT=production`, `MONGODB_CONNECTION_STRING`, `ALLOWED_ORIGINS`, `ADMIN_API_KEY` (opcional hasta que se decida activarla), `DISABLE_SCRAPING=1` (solo api). Frontend (Vercel): `VITE_API_BASE`, `VITE_SCRAPER_BASE`. Plantilla: `.env.example`.

## Despliegue automático (CI → Render)
Al integrar en `main`, `ci.yml` ejecuta los tests y luego llama a los *Deploy Hooks* de Render. Cada hook es un secreto de GitHub **opcional**: si falta, ese paso avisa (`::warning`) y se omite, no rompe el pipeline. (Antes, con el secreto sin definir, `curl` fallaba con *URL rejected: Malformed input to a URL function*.)
1. Render → servicio `basketlab-api` → *Settings → Deploy Hook* → copiar la URL.
2. GitHub → *Settings → Secrets and variables → Actions → New repository secret* → `RENDER_DEPLOY_HOOK_URL` = esa URL.
3. Repetir con `basketlab-scraper` → secreto `RENDER_SCRAPER_DEPLOY_HOOK_URL`.
**Comprobación posterior (#111)**: tras los hooks, `scripts/post_deploy_check.py --sha $GITHUB_SHA` espera (hasta **40 min**: el plan gratuito arranca en frío y a veces tarda 20-25 min en desplegar, #269) a que `GET /api/v1/health` informe del commit empujado (`RENDER_GIT_COMMIT`; el deploy es asíncrono y hasta entonces responde la versión anterior) y exige que `GET /api/v1/health/db` esté conectado. Un fallo deja `main` en rojo con la causa clasificada (`auth_failed`, `unreachable`…). Necesita la **variable** (no secreto) de GitHub `RENDER_API_URL` = URL pública de `basketlab-api` (*Settings → Secrets and variables → Actions → Variables*); sin ella se omite con un aviso. **Varios merges seguidos (#269)**: si la API ya sirve un commit **más nuevo que contiene** el comprobado (lo pregunta a la API de comparación de GitHub con `GITHUB_TOKEN`), el check pasa con la nota «superado por un despliegue más nuevo» y comprueba igualmente la base de datos; además el job de despliegue tiene `concurrency: deploy-render` con `cancel-in-progress`, así que el run de un commit antiguo que sigue esperando se **cancela** (gris) cuando llega uno nuevo en lugar de fallar. Sigue en rojo lo que es un fallo real: la API sirve un commit anterior tras los 40 min (el mensaje manda a mirar el panel de Render: ¿build fallido o en cola?) o la base de datos no conecta. Los hooks de despliegue están sin definir a propósito (Render despliega solo con cada push) y el job solo espera.
Si Render ya despliega solo en cada push (*Auto-Deploy* activado en el servicio), los hooks son redundantes y se pueden dejar sin definir: elige una sola vía para no desplegar dos veces.

## Grabar partidos de FEB en directo (feb-record.yml)
Para registrar el feed real de partidos (datos para calibrar el motor live, #118) edita `config/feb_watchlist.json` y haz PR a `main`: `calendars` = calendarios de FEB que se vigilan (los de `calendario.aspx?g=…&t=…&nm=…`); `teams` = ids de equipo (**todos sus partidos**; hoy `1008631` = MIPELLETYMAS B.F. LEON); `matches` = códigos sueltos (`Partido.aspx?p=<código>` o la lista de *Preparación live*); `competitions` = calendarios cuyos partidos se graban **todos**. Para una sola vez, sin tocar la lista: *Run workflow* con `codes` (grabar ya), `teams` o `competition` (URL del calendario). Id de un equipo: enlace `Equipo.aspx?i=<id>` del calendario. Desde entonces el workflow lo graba solo: lanza el job entre 3 h antes y 2 h después del inicio (GitHub ejecuta el `schedule` pocas veces al día, por eso la ventana es amplia y el planner también corre tras cada *Atlas refresh*; ver [LIVE.md](LIVE.md)). Resultado: GitHub → *Actions* → *FEB live recorder* → la ejecución → **Artifacts** `recording-<código>` (y el informe en *Summary*). **Grabar ya** (sin tocar la lista): *Actions → FEB live recorder → Run workflow* con el código. Local: `python -m src.live_prep.recorder record --match <código> --start-at <ISO UTC>` y `python -m src.live_prep.recording_report recordings/<código> --replay`. Consejo: añadir el partido a la lista con **más de una hora de antelación** (el planner lo ve en la siguiente pasada de 15 min).

## Mantener Atlas al día (atlas-refresh.yml)
Atlas solo contiene lo que alguien haya scrapeado contra él; el workflow `atlas-refresh.yml` lo automatiza (issue #177): 3 veces al día (05:30, 13:30, 21:30 UTC) y a mano (*Run workflow*) ejecuta `run_atlas_refresh.py`, que scrapea de FEB las competiciones de `config/atlas_refresh.json` (incremental: solo partidos terminados que no estén guardados) y las compara con el calendario de FEB. El run queda **en rojo** si una competición falla o aún faltan partidos jugados; el resumen del run lista los códigos que faltan.
Puesta en marcha (una vez):
1. Atlas → *Database Access* → usuario con rol `readWrite` sobre `BASKETBALL` (puede ser distinto del de la API, que solo necesita lectura si no se scrapea desde Render).
2. Atlas → *Network Access* → permitir `0.0.0.0/0` (las IP de GitHub Actions cambian en cada run; la protección es la contraseña del usuario).
3. GitHub → *Settings → Secrets and variables → Actions* → secreto `ATLAS_WRITE_URI` = cadena de conexión completa de ese usuario (nunca en el chat ni en el repo).
4. Lanzar el workflow a mano y revisar el resumen. Sin el secreto, el run falla con un mensaje claro (código 2).
Añadir una competición/temporada: nueva entrada en `config/atlas_refresh.json` (mismos campos que el scrape de la página Admin: `competition_url`, `season_value`, `group_value`, `year` y las tres etiquetas que forman el nombre de la colección). Si Atlas estuvo **pausado** por inactividad, hay que reanudarlo en Atlas (los síntomas son `unreachable` en `/api/v1/health/db`).

## Rellenar `DERIVED` en partidos ya guardados (#372)
Los partidos que entran por el scrape (también el refresco de Atlas) llevan `DERIVED` (posesiones exactas y rebotes/pérdidas validados) desde que se insertan. **El workflow *Atlas refresh* lo rellena solo** (último paso, tras cada scrape, aunque el refresco salga en rojo; usa `ATLAS_WRITE_URI`; #382): idempotente, solo toca los partidos sin la versión actual; recorre todas las colecciones de partidos, así que su coste crece con el tamaño de la base (hoy despreciable; si llegara a pesar, indexar `DERIVED.v`). A mano, para los guardados antes o si sube `DERIVED_VERSION` (v2 en #352: puntos por origen; v3 en #353: periodos; v4 en #354 y #355: situaciones y tiempos muertos; v5 en #390: fiabilidad por impacto; v6 en #398: contraataque estimado (**sin la v5 los cuatro endpoints salen vacíos y sin la v6 `points-by-origin`**); **hasta rellenarlos `/possessions/{collection}/points-by-origin`, `/by-period`, `/situations` y `/timeouts` salen vacíos** (Atlas se rellena solo en el siguiente *Atlas refresh*)), se rellenan con `python run_backfill_derived.py [--collection NOMBRE]` (idempotente; solo añade el campo; deshacer: `updateMany({}, {$unset: {DERIVED: ""}})`). Contra Atlas: define `MONGODB_CONNECTION_STRING` en la sesión (PowerShell: `$env:MONGODB_CONNECTION_STRING = '…'`, comillas simples; usuario y contraseña con caracteres especiales codificados con `urllib.parse.quote_plus`; sin la variable usa `db_credentials.txt`, o sea la BD local). Sin `DERIVED` los pipelines usan el respaldo del boxscore. Alternativa si se vacía una colección: el workflow *Atlas refresh* (*Run workflow*) la recrea desde FEB con `DERIVED`.

## Colección `HISTORICAL` (multifase, predictivo) y las posesiones (#379)
Sus filas por equipo y partido se calculan al ingerir (`POST /api/v1/historical/ingest`, con `DERIVED` si el partido lo trae o calculado desde el pbp). Los partidos ingeridos **antes** de #372 conservan la estimación antigua (0,45) hasta que se vuelven a ingerir con los mismos parámetros: la ingesta es idempotente (`(match_id, team_id)` se actualiza, no se duplica).

## Evaluar las reglas de alerta (rule-evaluation.yml)
*Actions → Rule evaluation → Run workflow* con la colección de la competición (`team` y `min_prior_games` son opcionales). Lee Atlas con `ATLAS_READ_URI` (usuario de solo lectura; `ATLAS_WRITE_URI` de reserva), reproduce todos los partidos como en directo desde los dos equipos y usa las grabaciones de `tests/recordings/` en lugar del feed simulado de su partido. El informe sale en el *Summary* y en el artefacto `rule-evaluation` (30 días): `report.md`, `evaluation.json`, `alerts.jsonl`. Detalle: [LIVE.md](LIVE.md) y [LIVE_RULES_CANDIDATES.md](LIVE_RULES_CANDIDATES.md).

## Publicar los paquetes live (live-packages.yml)
Tras cada refresco de Atlas, `live-packages.yml` construye los paquetes cifrados de los próximos partidos del club (`config/package_publish.json`) y los publica en la rama `live-packages` (un solo commit forzado, ver [LIVE.md](LIVE.md)). Puesta en marcha (una vez): secreto `PACKAGE_PASSWORD` (≥ 8 caracteres, el mismo que se escribe una vez en la app; el repo es público, usa una contraseña larga) y, mejor, `ATLAS_READ_URI` con un usuario de Atlas de **solo lectura** (si no existe se usa `ATLAS_WRITE_URI`). Sin ellos el run falla con código 2. Si el workflow no se dispara tras el refresco, lanzarlo a mano (*Run workflow*). Además de los rivales del club publica la **jornada completa de cada competición** de `config/atlas_refresh.json` (`rounds/*.bpkgz`, ~70 KB por jornada y competición; `"rounds": false` en `config/package_publish.json` lo desactiva). El tiempo límite del job es de 60 minutos: cada competición cuesta una pasada por sus partidos (LF Challenge, ~14 s).

## Memoria (límite de 512 MB en Render free)
Un documento de partido pesa ≈ 1 MB en memoria de Python y la app completa ≈ 170 MB en reposo (más: scikit-learn +125 MB al primer uso predictivo, matplotlib +45, pandas +50). Medidas tomadas (issue #163):
- **Un solo worker** de uvicorn por defecto (`src/api/runtime.uvicorn_workers`; `WEB_CONCURRENCY` lo sube, tope 4). Antes `run_api.py` lanzaba 4 en Linux → ~500-700 MB en reposo y OOM intermitente al desplegar.
- `MALLOC_ARENA_MAX=2` (menos fragmentación) y `pip install --no-cache-dir` en el build (`render.yaml`). Si los servicios no se crearon desde el Blueprint, poner `WEB_CONCURRENCY=1` y `MALLOC_ARENA_MAX=2` a mano en *Environment*.
- Listado de partidos con **proyección** (no cargar documentos completos), zonas de liga **en streaming** y caducidad (15 min) de los ZIP del informe semanal sin descargar.
- **Diagnóstico**: poner `LOG_MEMORY=1` en el servicio y redeploy; los logs mostrarán `WARNING basketlab.memory GET /ruta rss 412 MB (+90 MB)` para peticiones que suben ≥ 25 MB (`LOG_MEMORY_DELTA_MB`) o dejan el RSS ≥ 350 MB (`LOG_MEMORY_HIGH_MB`). Contrastarlo con *Metrics → Memory* del servicio en Render.
- Regla de código: nunca `find({})` sin proyección sobre colecciones de partidos; iterar cursores/generadores en vez de materializar listas de documentos o tiros.
Si aun así se supera el límite: plan de pago de Render (1 GB+) o separar los endpoints predictivos (scikit-learn) en otro servicio.

## App Android (BasketLab Live): APK, firma y publicación
La app (`apps/live-android`) se compila **en GitHub Actions** (`.github/workflows/live-android.yml`); no hace falta Android Studio ni Java en local. Cada PR/push que toque la app deja el APK como artefacto del workflow (requiere sesión de GitHub para descargarlo). Para tener un **enlace directo** (el repo es público) se publica una Release con una etiqueta.

### Publicar una versión
```bash
git tag live-android-v0.1.0
git push origin live-android-v0.1.0
```
El workflow compila, firma y publica **dos** releases:
- **Por versión** (histórico): `https://github.com/kanijoman/BasketLab/releases/tag/live-android-v0.1.0`, con `basketlab-live-0.1.0.apk`. Ambas se publican como *prerelease*: así nunca son la "latest" del repo (`make_latest:false` no basta: GitHub elegiría la más reciente).
- **Enlace fijo a la última** (`live-android-latest`, se recrea en cada etiqueta): `https://github.com/kanijoman/BasketLab/releases/download/live-android-latest/basketlab-live.apk`. Es el que conviene guardar en el móvil/tablet.
No uses `releases/latest` para la app: apunta a la última release **de todo el repo** (hoy solo hay releases del APK, pero si se publicara otra cosa dejaría de servir). Convención: etiquetas `live-android-vX.Y.Z` para el APK (y `web-v*` si algún día hay releases de la web); listado solo del APK: `https://github.com/kanijoman/BasketLab/releases?q=live-android`. El `versionCode` sube solo (número de ejecución del workflow), así que cada APK puede instalarse **encima** del anterior.

### Ciclo de publicación: cada viernes por la mañana
Decisión del 13/10: **cada viernes por la mañana** se publica una versión con todo lo integrado hasta ese momento (puede haber partidos el viernes por la tarde o noche, así que no más tarde) y el staff se actualiza con el **botón de la propia app** (*Actualizar* en el aviso superior o *Buscar actualización* en *Acerca de*). La versión sube el número menor (0.2.0 → 0.3.0 → 0.4.0…). Con cada versión el workflow sube además `latest.json` a la release fija `live-android-latest`: es lo que lee la app para saber si hay una más nueva (ver [LIVE.md](LIVE.md)).
**Publicación automática (#279)**: el workflow `live-android-release.yml` se ejecuta **los viernes a las 07:00 UTC** (las 09:00 en Madrid con horario de verano, las 08:00 en invierno) y decide con `scripts/live_android_release.py` (con tests):
- **¿Hay algo que publicar?** Compara con la última etiqueta `live-android-v*` (la de mayor versión, no la más reciente) y solo cuentan los cambios que acaban en el APK: `apps/live-android`, `src/live_core`, `design`, `tests/live_vectors`, `tests/recordings` y `src/JSON_samples/feb_game.json`, **sin** documentos ni tests. Sin cambios no publica nada y lo dice en el resumen del run.
- **Versión**: la última + 1 en el número menor. A mano (*Actions → Live Android release → Run workflow*): `version` (X.Y.Z, posterior a la última) fuerza otra, `force` publica aunque no haya cambios y **`dry_run`** enseña la versión y las notas que se publicarían **sin publicar nada** (para ensayar).
- **Notas**: los títulos de los PR integrados desde la anterior (`generate-notes` de la API de releases), completos en la release y resumidos (hasta 8 y 600 caracteres) en el `latest.json` que muestra la app.
- **Cómo publica**: una etiqueta creada con el `GITHUB_TOKEN` **no dispara otros workflows**, así que no etiqueta: lanza `live-android.yml` con la versión y las notas (`workflow_dispatch`). Ese workflow pasa sus tests, compila **desde `main`** (solo `main`: desde otra rama falla), firma con la clave de la release y crea la etiqueta y las dos releases (por versión y `live-android-latest`). El `versionCode` sigue siendo el número de ejecución de `live-android.yml`, que solo crece (uno menor haría que Android rechazara la actualización).
- Empujar una etiqueta `live-android-vX.Y.Z` a mano sigue funcionando como antes. Si algo falla (tests rojos, firma), el run de `live-android.yml` lo dice y no se publica nada; se corrige y se vuelve a lanzar a mano.

**La primera vez** (la versión que trae el botón, la 0.3.0): la 0.2.0 instalada no sabe actualizarse, así que se instala a mano como abajo; las siguientes, con el botón. Android siempre pide confirmar la instalación y, la primera vez, permitir apps desconocidas.

### Instalar en el móvil / tablet (una vez por dispositivo)
1. Abrir el enlace de la Release en el navegador del dispositivo y descargar el `.apk`.
2. Android pedirá permitir **"Instalar apps desconocidas"** para ese navegador (o gestor de archivos): *Ajustes → Apps → [navegador] → Instalar apps desconocidas → Permitir*. No hace falta modo desarrollador ni depuración USB.
3. Abrir el APK y pulsar *Instalar*. Si Play Protect avisa de "app no verificada", elegir *Instalar de todos modos*.
4. Actualizar = descargar el APK nuevo e instalarlo encima (misma clave de firma, `versionCode` mayor). Si el dispositivo es de un MDM del club, puede tener bloqueadas las fuentes desconocidas.

### Clave de firma propia (recomendado antes de la primera tablet "de verdad")
Sin los secretos de abajo el workflow firma con una clave de depuración **efímera**: el APK se instala, pero el siguiente build no podrá actualizarlo (habría que desinstalar la app y se pierden sus datos). Con la clave propia, todas las versiones son actualizaciones válidas.
1. Generar el almacén (necesita un JDK; `keytool` viene con él, p. ej. `winget install Microsoft.OpenJDK.21`):
   ```bash
   keytool -genkeypair -v -keystore basketlab-release.keystore -alias basketlab -keyalg RSA -keysize 2048 -validity 10000
   ```
   Anota las contraseñas. **Guarda una copia del `.keystore` y las contraseñas en un sitio seguro: si se pierden no se podrá actualizar la app instalada.** No lo commitees (`*.keystore` está en `.gitignore`).
2. Codificarlo en base64 (PowerShell): `[Convert]::ToBase64String([IO.File]::ReadAllBytes("basketlab-release.keystore")) | Set-Clipboard`
3. GitHub → *Settings → Secrets and variables → Actions → New repository secret*, cuatro secretos:
   `ANDROID_KEYSTORE_BASE64` (el base64), `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` (`basketlab`), `ANDROID_KEY_PASSWORD`.
4. Publicar una versión nueva (etiqueta). Si ya había una app instalada con la clave efímera: desinstalarla una vez.
Rotar la clave implica desinstalar y reinstalar en todos los dispositivos.

## Futuro
La gestión real de usuarios y roles (sustituir la clave única) está planificada y aplazada en la épica #153.
