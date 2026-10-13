# Testing (para Claude)
Regla de trabajo (TDD, regresión por bug): [CLAUDE.md](../CLAUDE.md). Este doc: cómo se prueba, qué hay y qué falta.

## Ejecutar
```bash
pytest -q                                   # backend completo (cobertura sobre src/ por defecto, pytest.ini)
# En local solo se ejecutan los tests de lo que se ha tocado (p. ej. `pytest -q --no-cov tests/test_live_core_*.py`); la suite completa tarda ≈ 6 min y la ejecuta el CI de GitHub en cada PR (regla de CLAUDE.md).
pytest tests/test_live_core_*.py -q --no-cov
cd frontend && npm run lint && npm run type-check && npm run test:run && npm run build
python tests/live_vectors/generate.py       # regenerar vectores live tras cambiar live_core
cd tests/pyodide && npm ci && node run_vectors.mjs   # motor dentro de Pyodide
```
Dependencias: `pip install -r requirements-dev.txt` (Render usa solo `requirements.txt`). Tests con marker `ml` (`test_backtesting`, `test_game_prediction`, `test_player_prediction`, `test_predictive`, 2 de `test_regression_formulas`) se **saltan** solos sin `scikit-learn`; en CI corren. Frontend en Windows: si vitest no arranca por el binding de rolldown, `rm -rf frontend/node_modules && npm ci`.

## Mapa de tests (≈ 117 archivos, 2.304 tests backend, cobertura ≈72 %; frontend 23 archivos / 146 tests)
- API (`TestClient`, `dependency_overrides[get_db]`): `test_api*.py`, `test_*_router.py`, `test_integration_api_services.py`, `test_lineups_sse.py`, `test_scraper_endpoints.py`.
- Servicios y BD con `mongomock` (sin red ni Mongo real): `test_services.py`, `test_rotation_service.py`, `test_repository_*`, `test_pipeline_builder.py`, `test_indexes.py`.
- PBP/posesiones: `test_possession_*`, `test_playbyplay_analyzer.py`, `test_pbp_*`. Predictivo (necesita sklearn): ver arriba. Informes/export: `test_pdf_generator.py`, `test_weekly_report*`, `test_individual_scouting.py`.
- Live: `test_live_core_*`, `test_live_prep_*`, `test_live_vectors.py`, `test_live_pyodide.py` (salta sin Node), frontera de imports sin BD (`test_live_core_boundary.py`).
- Informes por reglas: `test_report_engine.py` (motor puro), `test_team_report_service_and_api.py` (renderer, servicio, endpoints JSON/PDF). Zonas vs liga: `test_zone_rating.py`, `test_shots_zone_compare.py`, `test_zone_analysis_relative.py`. FBCYL: `test_fbcyl_zones.py`, `test_fbcyl_zone_pipeline.py`.
- Seguridad: `test_admin_auth.py` (clave de admin, 503 en producción sin clave, clasificación de rutas de escritura).
- Memoria: `test_memory_mitigations.py` (workers, proyección del listado de partidos, zonas de liga en streaming, caducidad de jobs, log de RSS, render.yaml).
- Refresco de Atlas: `test_atlas_refresh.py` (scrape incremental, errores por competición, informe, configuración, import limpio del CLI) y `test_data_freshness.py`/`test_db_health.py`.
- Publicación de paquetes: `test_package_publisher.py` (un paquete descifrable por rival, índice, rivales repetidos, fallos aislados, limpieza, configuración, CLI sin credenciales).
- Tabla de posesiones: `possessions/columns.test.tsx` (vistas Resumen / Estilo propio / Rival, CSV completo, nombre de equipo no recortado), `PossessionsPage.test.tsx`, `DataTable.test.tsx` (cabeceras de grupo).
- Combinaciones: `test_lineups_time_filters.py` (regresión del filtro «Últimos N días» —el corte era una cadena y Mongo no la casa con una fecha— , filtro «Último partido» con `$sort`/`$limit` en Mongo y mínimo de partidos acotado a los analizados) y `client.test.ts` (opciones de período).
- Ritmo live: `test_live_core_pace.py` (ritmo, +/- sobre el habitual, proyección, prórroga, paquetes antiguos, serialización), `test_live_prep_builder.py` (ritmo habitual por equipo) y en la app `PaceCard.test.tsx`, `App.test.tsx` y el e2e (la tarjeta pasa de «calculando» a la proyección con Pyodide real).
- Grabación reproducible (#174): `test_recorded_feed.py` (formato y empaquetado con una grabación sintética: reconstrucción exacta, 404 por endpoint, correcciones), `test_recorded_feed_real.py` (fixture real de Zamora–León: 353 frames, 404 de mitad de partido, el motor la digiere y la proyección de ritmo), `test_live_core_fake_feb_recording.py` (el servidor falso con el ritmo real) y `test_live_core_engine_corrections.py` (líneas corregidas en directo).
- Partido real en la app (#174): `test_live_core_session_recording.py` (`play`, 404 de mitad de partido, partido completo = 38-59, entradas Pyodide), `bridge.test.ts` (lo mismo en Pyodide real), `client.test.ts`, `App.test.tsx` (selector, esperando / FEB no responde / alertas, vuelta al ejemplo, error de carga) y el e2e del partido completo a 300× en móvil.
- Modo en directo de la app (#217): `feed/febClient.test.ts` (token, direcciones, renovación ante 401, 404 y JSON inválido), `feed/liveFeed.test.ts` (espera, 404 de mitad de partido, endpoint suelto que falla, error de red, estado final tardío, fallo del motor, parar), `feed/defaultHttp.test.ts` (HTTP nativa frente a `fetch`), `feed/liveFeed.recording.test.ts` (**el partido real completo** contra un FEB falso con la grabación y el motor en Pyodide: 38-59, corte de 404, renovación de token), `ui/LiveConnect.test.tsx`, `ui/AppLive.test.tsx` y un e2e en móvil (la app contra un FEB falso interceptado con CORS y *preflight*, a 240×).
- Partido por defecto, local/visitante y logos (#223, #228, #230): `test_live_core_state.py` (`home_id`, también tras el JSON que ordena claves y en la grabación real), `test_live_core_session_recording.py` (`meta.home_id`), app: `ui/teams.test.ts`, `ui/TeamLogo.test.tsx`, `ui/Scoreboard.test.tsx`, `engine/demo.test.ts`, `ui/App.test.tsx` (el último partido grabado por defecto, reserva al ejemplo, cambio de partido, error de carga), `apps/live-android/scripts/lib/manifest.test.mjs` y `apps/live-android/scripts/lib/logos.test.mjs` (manifiesto ordenado, descarga y redimensionado de escudos con red simulada) y los e2e en móvil (abre en Zamora–León con el local a la izquierda).
- Jerarquía de alertas (#229): `test_live_core_alert_severity.py` (severidad por regla y umbral, reparto 1/10/16 sobre la grabación real), app: `ui/AlertList.test.tsx` y el e2e de la grabación real (contador, informativas colapsadas).
- Claves únicas por emisión (#234): `test_live_core_rearm_keys.py` (una alerta re-armada sale como `key#n`; las 27 alertas de la grabación real tienen claves distintas) y, en la app, `feed/liveFeed.recording.test.ts` comprueba lo mismo con Pyodide real.
- Registro de eventos y ventanas (#237): `test_live_core_event_log.py` (cada evento deja su entrada con jugador; el registro del partido real cuadra con los totales de equipo: intentos, aciertos, puntos, robos, tiempos muertos y pérdidas de equipo) y `test_live_core_windows.py` (estadísticas de ventana, sequías, rachas, causas ordenadas y entradas antiguas de 4 elementos); en los vectores, `windows.*`.
- Registro de reglas y `rules_off` (#236): `test_live_core_rule_registry.py` (ids únicos, cada regla se apaga sola sin tocar las demás, `rules_off` desde el JSON del paquete, ids desconocidos ignorados) y un caso `advice.sequence` con `rules_off` en los vectores (Pyodide lo reproduce igual).
- Feedback del staff (#235), app: `feedback/store.test.ts` (registro, veredicto, persistencia por partido, almacenamiento roto), `ui/AlertCard.test.tsx` (botones), `ui/FeedbackPanel.test.tsx` (copiar, descargar, borrar) y `ui/App.feedback.test.tsx` (de la alerta mostrada al JSON guardado).
- Workflows: `test_workflows_yaml.py` (todos los `.github/workflows/*.yml` son YAML válido).
- Paquete live: `test_live_package_api.py` (generación, límites, contraseña), `test_live_prep_crypto.py` (+ fixture `demo.bpkg`); web `LivePrepPage`/`livePackage`; app `package/*` (WebCrypto sobre el fixture de Python, IndexedDB), `PackagePanel` y un e2e de importación en Chrome real.
- Canario FEB: `test_feb_canary.py` (esquema, invariantes, CLI y códigos de salida) y `feb-canary.yml` (diario; descarga real de FEB, abre issue `canary` ante deriva).
- Partidos en directo: `test_calendar_parser.py` (fixture real recortado `tests/fixtures/feb_calendar_snippet.html`), `test_match_schedule_service.py`, `test_live_matches_api.py` (endpoint, partido en el paquete, metadatos al hacer scrape).
- Grabador FEB: `test_feb_recorder.py` (bucle de sondeo con FEB simulado y reloj falso), `test_feb_recorder_plan.py` (qué grabar ahora, CLI, import limpio), `test_recording_report.py` (cadencia, retraso, replay) y `feb-record.yml` (planner + matriz + concurrencia).
- Guardas: `test_no_llm_dependencies.py`, `test_no_hardcoded_secrets.py`, **`test_docs_consistency.py`** (docs sincronizados con el código).
- Fixtures: `tests/conftest.py` (`feb_game_doc`, `fbcyl_game_doc`, `mock_*_db`; limpia cachés bajo ambos alias de import), `tests/live_helpers.py`, `tests/db_helpers.py` (`new_mock_db`: única forma de crear una BD mongomock).

## CI (`.github/workflows`)
`ci.yml`: backend (`pytest --cov --cov-fail-under=70`, Python 3.11, instala `requirements-dev.txt`; base medida 71,8 %; subir el umbral solo cuando la cobertura mejore de forma estable), frontend (`npm ci`, lint, type-check, vitest, `npm run build`), job `e2e-web` (smoke Playwright, ver abajo), deploy a Render solo en push a `main` (necesita `e2e-web`) con comprobación posterior (`scripts/post_deploy_check.py`, ver OPERATIONS). `live-vectors.yml`: regenera vectores (falla si `git diff`), pruebas de referencia sin `conftest`, vectores en Pyodide.

## Evaluación (estado actual) y mejoras
| Hueco | Prioridad | Estado |
|---|---|---|
| Tests de ML y deps de test mezcladas con runtime | alta | **hecho** (marker `ml`, `requirements-dev.txt`) |
| Sin `vite build` ni gate de cobertura en CI | alta | **hecho** (build + `--cov-fail-under=70`, base 72 %) |
| Router `rotaciones` sin test; `analysis_predictive` | alta | **hecho** (`test_rotaciones_router.py`; predictive ya estaba cubierto) |
| `fetch` crudo en páginas ignoraba `VITE_API_BASE`; `getPlayerRankings/Radar` a rutas inexistentes | media | **hecho** (todo vía `client.ts`; `client.test.ts`) |
| Frontend: sin tests de páginas ni del SSE de `client.ts` | media | pendiente (bajo retorno; preferir smoke e2e) |
| Sin **contrato** back↔front (0 `response_model`; tipos TS a mano) | media (más trabajo) | hoja de ruta: modelos Pydantic + OpenAPI → tipos TS |
| Sin e2e ni smoke contra servidor real; sin health-check post-deploy | media | **hecho** (#111: `frontend/e2e/smoke.spec.ts` + `scripts/post_deploy_check.py`) |
| `npm run lint` roto (no había config) | baja | **hecho** (`eslint.config.js`, `--max-warnings 0` en CI: sin avisos) |
| `mongomock.MongoClient()` ad hoc en ~20 tests | baja | **hecho** (`tests/db_helpers.new_mock_db`, vigilado por `test_mongomock_usage.py`) |
Frontend: compensa testear `client.ts` y helpers puros; testear páginas enteras con mocks rinde poco (mejor un smoke e2e).

## App Android (`apps/live-android`): ya montado en `live-android.yml`
Descarga de paquetes publicados: `remote.test.ts` (índice, SHA-256, offline), `passphrase.test.ts`, `RemotePackages.test.tsx`; los tests de `App` y el e2e interceptan la red de la lista. `test-setup.ts` aporta un `localStorage` en memoria.
## Smoke e2e de la web (#111)
`frontend/e2e/smoke.spec.ts` (Playwright, Chromium escritorio 1280×800): inicio (lista la competición, **no** muestra `COLLECTION_META`), tabla de equipos, posesiones (vista Resumen por defecto, vista Estilo propio con cabeceras agrupadas, nombre completo del equipo, sin scroll horizontal) y salud de la API. Corre contra el **build de producción** (`vite preview`, que proxea `/api`) y la **API real sobre mongomock** (`tests/e2e_web/serve_api.py`: parchea `pymongo.MongoClient`, siembra el partido de ejemplo ×3 y sirve con uvicorn en :8010; `test_e2e_web_server.py` evita que se pudra). Local: `cd frontend && E2E_PYTHON="<ruta a python>" npm run e2e` (reutiliza Chrome; en CI `npm run e2e:ci` tras `npx playwright install --with-deps chromium`). El job `e2e-web` de `ci.yml` es requisito del deploy; al fallar sube `frontend/test-results` como artefacto. Ampliar con un flujo nuevo = una prueba más en ese fichero (la semilla es una sola competición).

Job `web` (type-check, vitest con Pyodide real vs vectores, build, Playwright Pixel 7) y job `apk` (Gradle, APK firmado, artefacto; release en tags `live-android-v*`). Local: `cd apps/live-android && npm ci && npm run test:run`; e2e local con Chrome instalado: `npm run e2e`. Pendiente del marco original: emulador Android (Maestro) y Firebase Test Lab. El canario diario de FEB (#136) ya existe (`feb-canary.yml`).

## Marco cloud para la app Android (diseño original)
Capas gratuitas en GitHub Actions/Google: pytest del motor → motor en Pyodide (hecho) → UI en perfiles Android de Playwright con FEB y Drive simulados (`fake_feb`) → APK en emulador con Maestro → Firebase Test Lab → App Distribution. Fluidez: motor en Web Worker; con reproducción ×30 y CPU ×4 más lenta contar tareas largas del hilo principal. Canario diario contra un partido FEB finalizado.

## Checklist manual (rescatado del plan antiguo)
Con API y frontend arrancados (Swagger en `localhost:8000/docs`): `GET /api/v1/historical/summary` con datos · `rival_adjusted` en una colección FEB y otra FBCYL (`adj_avg = raw_avg + adj`) · `elasticity/train` (422 sin datos; 12 modelos con datos) y `predict` (IC coherente; 404 equipo inexistente) · `montecarlo/<team>` (`n_games` ≤ 10 y `n_simulations` ≥ 100, si no 422; `win_prob` en [0,1]) · regresión: `GET /`, `teams/<col>/stats`, `players/<col>/stats`, `collections/list` · casos: FEB y FBCYL, equipo con < 10 partidos (error controlado), Mongo caído (error gestionado, no 500) · descargar en `Informes`: ZIP semanal y DOCX de scouting individual.
