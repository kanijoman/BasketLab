# Arquitectura (para Claude)
Flujo: **frontend → API (routers) → servicios → repositorio → MongoDB**. Nada de BD en el frontend. Operaciones y clave de admin: [OPERATIONS.md](OPERATIONS.md). Detalle de datos: [DATA_FORMATS.md](DATA_FORMATS.md); motor live: [LIVE.md](LIVE.md).

## Paquetes `src/`
| Paquete | Qué hay |
|---|---|
| `src/api` | FastAPI: `app.py` (todos los routers, CORS), `scraper_app.py` (solo scrape+collections), `deps.py` (`get_db`, handler único con `lru_cache`, 503 si no hay Mongo), `routers/` |
| `src/services` | lógica de negocio (ver abajo) |
| `src/database` | conexión, repositorios, pipelines de agregación, índices |
| `src/scraper` | clientes FEB/FBCYL: token JWT, API, calendario HTML |
| `src/pbp` | parsers de play-by-play y posesiones **sin BD** (los reutiliza el motor live) |
| `src/report_engine` | informes por reglas (sin LLM, funciones puras): `catalog` (estadísticas), `rules` (cuartiles, diferencial vs mediana, CV), `zones` (zonas calientes/frías), `templates` (frases por tema), `engine.build_team_report`, `html_renderer` (para PDF), `config.ReportConfig` (umbrales por confirmar) |
| `src/live_core` | motor de partido en vivo, biblioteca estándar (corre en la tablet con Pyodide) |
| `src/live_prep` | generación y cifrado de paquetes de preparación (usa Mongo) |
| `src/shotcharts` | cancha FIBA, zonas (shapely), visualizadores; `feb_zones` (geometría de 10 zonas + conteo por zona, usado por el router y los informes), `fbcyl_zones` (mismos conteos desde las coordenadas por jugador de FBCYL), `zone_rating` (valoración de zona vs media de liga), `league_zones` (base de liga para los PNG de `ZoneAnalyzer`) |
| `src/stats` | calculadoras (StatsCalculator, avanzadas, jugador) |
| `src/utils` | `collection_utils` (`is_fbcyl`), `numeric_utils`, `team_utils` |
| `src/visualization` | radar chart |
`src/JSON_samples/` = documentos reales de ejemplo (FEB y FBCYL) para tests. `apps/live-android/` = app móvil/tablet del motor live (fuera de `src/`; ver [LIVE.md](LIVE.md)).

## Routers (`src/api/routers`, prefijo `/api/v1/<x>`)
`collections` · `teams` · `players` (incluye IN/OUT y `together`) · `lineups` (REST + SSE `/stream`) · `scrape` (también en el servicio scraper) · `shots` (zonas; `?compare=league` añade `rating`/`league_pct`/`delta_pp`/`low_sample`) · `possessions` · `live_package` (`/api/v1/live/package`: genera el paquete cifrado de preparación live como job en segundo plano; público pero **un solo job a la vez** y con caducidad de 15 min, ver [LIVE.md](LIVE.md)) · `team_report` (informe automático por reglas JSON/PDF, modos `own`/`rival`; en `/reports/team-report/{collection}`) · `reports` (informe semanal ZIP, PDF/DOCX, `export-pdf`, `individual-scouting/docx`) · `historical` · `analysis` + `analysis_predictive` (ambos bajo `/analysis`: ajuste por rival, elasticidades, Monte Carlo, backtesting, predicción) · `matches` · `multi_phase` (`/multi`) · `rotaciones` (REST + SSE). **Seguridad**: no hay usuarios ni roles; las rutas destructivas, de ingesta y de entrenamiento (`DELETE collections`, `scrape/start`, `historical/ingest*`, `elasticity/train*`) exigen la cabecera `X-Admin-Key` = `ADMIN_API_KEY` (guía de activación en [OPERATIONS.md](OPERATIONS.md); `src/api/security.require_admin`; en producción sin la variable responden 503, en desarrollo quedan abiertas). `tests/test_admin_auth.py` obliga a clasificar todo endpoint de escritura nuevo (protegido o en la lista pública explícita). El resto de la API es de lectura/cómputo y público.

## Servicios (`src/services`)
- Stats: `team_stats_service`, `player_stats_service`, `evolution_service`, `match_analysis_service`, `multi_phase_service`, `lineup_service`, `rotation_service`, `rival_adjusted_service`, `collection_service`, `_consistency_calculator`.
- Predictivo (scikit-learn): `elasticity_service` (+`_elasticity_models`, `_ridge_helpers`, `_feature_builders`, `_gbm_models`), `monte_carlo_service`, `backtesting_service`, `game_prediction_service`, `player_prediction_service`, `season_projection_service`, `live_history_adapter`.
- Datos históricos: `historical_ingestion_service`, `_feb_normalizer`, `_fbcyl_normalizer`, `_historical_derived`.
- Informes/export: `report_service`, `weekly_report_service` (+`_weekly_report_helpers`), `individual_scouting_service` (+`_scouting_docx_helpers`, `_scouting_formatters`), `pdf_generator`, `possession_export_service`, `pbp_quality_service`, `player_data_fetcher`, `team_report_service` (datos → `report_engine`).

## Base de datos (`src/database`)
- `db_config.get_mongodb_connection_string()`: env `MONGODB_CONNECTION_STRING` → `src/database/db_credentials.txt` (no versionado) → valor por defecto. BD `BASKETBALL`, un `MongoDBHandler` (fachada) sobre `BasketballRepository` (+mixins `repository_games/_inout/_lineup/_possession`).
- Colecciones de partidos: `{competición}_{temporada}_{grupo}` saneado (`get_collection_name`); prefijo `FBCYL_` = formato FBCYL (`is_fbcyl`). Además `HISTORICAL` y `ELASTICITIES` (modelos entrenados).
- `aggregation/` (pipelines FEB y FBCYL), `indexes.py` (`IndexManager`, siempre `background=True`).
- Calculadoras PBP de BD: `inout_calculator`, `lineup_extractor`, `lineup_stats_calculator`, `possession_analyzer`.

## Frontend (`frontend/src`)
Vite + React + TS + TanStack Query + Tailwind + Recharts/D3; `api/client.ts` (todas las llamadas; `BASE` = `VITE_API_BASE`+`/api/v1`, scraper = `VITE_SCRAPER_BASE`), SSE con `EventSource` en lineups y rotaciones, `context/` (`CollectionContext`, `AuthContext` stub), `lib/adminKey` + `AdminKeyField` (clave de admin en `sessionStorage`, cabecera `X-Admin-Key`), `components/ui` (StatCard, FilterBar, DataTable, ExportButton…), `lib/` (utils, statLabels, exportDom, pdfLayout, zoneRating). Rutas `/:collection/{teams,players,evolution,shots,rankings,report,team-report,live-prep,possessions,inout,lineups,rotaciones,…}` y `/admin`. Proxy dev `/api` → `localhost:8000`.

## Despliegue y config
- `render.yaml`: `basketlab-api` (`python run_api.py`, `DISABLE_SCRAPING=1`) y `basketlab-scraper` (`python run_scraper.py`), plan free, Frankfurt. Frontend en Vercel (`vercel.json`: rewrite SPA). CI (`.github/workflows/ci.yml`): tests + deploy hook de Render en push a `main`.
- Env backend: `MONGODB_CONNECTION_STRING`, `ALLOWED_ORIGINS`, `ADMIN_API_KEY` (misma en api y scraper), `WEB_CONCURRENCY` (workers, 1 por defecto), `MALLOC_ARENA_MAX`, `LOG_MEMORY` (ver [OPERATIONS.md](OPERATIONS.md#memoria-límite-de-512-mb-en-render-free)), `ENVIRONMENT`, `DISABLE_SCRAPING`, `BASKETLAB_DEV`, `PORT`. Frontend: `VITE_API_BASE`, `VITE_SCRAPER_BASE`. Ejemplo en `.env.example`.

## Rutas de import
Usa siempre `src.…`. Los parsers PBP viven en `src/pbp` (sin BD); los antiguos shims se eliminaron (`tests/test_pbp_isolation.py` lo vigila). `tests/conftest.py` limpia cachés bajo ambos alias por compatibilidad con tests antiguos.

## Deuda conocida de arquitectura
Ver [ROADMAP.md](ROADMAP.md).
