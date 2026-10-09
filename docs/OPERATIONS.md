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
| CORS / `OPTIONS` bloqueado | `ALLOWED_ORIGINS` no incluye la URL de Vercel | Ajustar `ALLOWED_ORIGINS` (la cabecera `X-Admin-Key` está permitida) |
| Funciona en local pero no en producción | en local no hay guarda (sin `ENVIRONMENT=production`) | Esperado |

## Variables de entorno (resumen)
Backend (Render): `ENVIRONMENT=production`, `MONGODB_CONNECTION_STRING`, `ALLOWED_ORIGINS`, `ADMIN_API_KEY` (opcional hasta que se decida activarla), `DISABLE_SCRAPING=1` (solo api). Frontend (Vercel): `VITE_API_BASE`, `VITE_SCRAPER_BASE`. Plantilla: `.env.example`.

## Despliegue automático (CI → Render)
Al integrar en `main`, `ci.yml` ejecuta los tests y luego llama a los *Deploy Hooks* de Render. Cada hook es un secreto de GitHub **opcional**: si falta, ese paso avisa (`::warning`) y se omite, no rompe el pipeline. (Antes, con el secreto sin definir, `curl` fallaba con *URL rejected: Malformed input to a URL function*.)
1. Render → servicio `basketlab-api` → *Settings → Deploy Hook* → copiar la URL.
2. GitHub → *Settings → Secrets and variables → Actions → New repository secret* → `RENDER_DEPLOY_HOOK_URL` = esa URL.
3. Repetir con `basketlab-scraper` → secreto `RENDER_SCRAPER_DEPLOY_HOOK_URL`.
Si Render ya despliega solo en cada push (*Auto-Deploy* activado en el servicio), los hooks son redundantes y se pueden dejar sin definir: elige una sola vía para no desplegar dos veces.

## Grabar partidos de FEB en directo (feb-record.yml)
Para registrar el feed real de partidos (datos para calibrar el motor live, #118) edita `config/feb_watchlist.json` y haz PR a `main`: `calendars` = calendarios de FEB que se vigilan (los de `calendario.aspx?g=…&t=…&nm=…`); `teams` = ids de equipo (**todos sus partidos**; hoy `1008631` = MIPELLETYMAS B.F. LEON); `matches` = códigos sueltos (`Partido.aspx?p=<código>` o la lista de *Preparación live*); `competitions` = calendarios cuyos partidos se graban **todos**. Para una sola vez, sin tocar la lista: *Run workflow* con `codes` (grabar ya), `teams` o `competition` (URL del calendario). Id de un equipo: enlace `Equipo.aspx?i=<id>` del calendario. Desde entonces el workflow lo graba solo: lanza el job entre 45 min antes y 30 min después del inicio. Resultado: GitHub → *Actions* → *FEB live recorder* → la ejecución → **Artifacts** `recording-<código>` (y el informe en *Summary*). **Grabar ya** (sin tocar la lista): *Actions → FEB live recorder → Run workflow* con el código. Local: `python -m src.live_prep.recorder record --match <código> --start-at <ISO UTC>` y `python -m src.live_prep.recording_report recordings/<código> --replay`. Consejo: añadir el partido a la lista con **más de una hora de antelación** (el planner lo ve en la siguiente pasada de 15 min).

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
