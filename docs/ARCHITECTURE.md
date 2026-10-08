# Arquitectura (para Claude)
Flujo: **frontend → API (routers) → servicios → repositorio → MongoDB**. Nada de BD en el frontend. Detalle de datos: [DATA_FORMATS.md](DATA_FORMATS.md); motor live: [LIVE.md](LIVE.md).

## Paquetes `src/`
| Paquete | Qué hay |
|---|---|
| `src/api` | FastAPI: `app.py` (todos los routers, CORS), `scraper_app.py` (solo scrape+collections), `deps.py` (`get_db`, handler único con `lru_cache`, 503 si no hay Mongo), `routers/` |
| `src/services` | lógica de negocio (ver abajo) |
| `src/database` | conexión, repositorios, pipelines de agregación, índices |
| `src/scraper` | clientes FEB/FBCYL: token JWT, API, calendario HTML |
| `src/pbp` | parsers de play-by-play y posesiones **sin BD** (los reutiliza el motor live) |
| `src/live_core` | motor de partido en vivo, biblioteca estándar (corre en la tablet con Pyodide) |
| `src/live_prep` | generación y cifrado de paquetes de preparación (usa Mongo) |
| `src/shotcharts` | cancha FIBA, zonas (shapely), visualizadores |
| `src/stats` | calculadoras (StatsCalculator, avanzadas, jugador) |
| `src/utils` | `collection_utils` (`is_fbcyl`), `numeric_utils`, `team_utils` |
| `src/visualization` | radar chart |
`src/JSON_samples/` = documentos reales de ejemplo (FEB y FBCYL) para tests.

## Routers (`src/api/routers`, prefijo `/api/v1/<x>`)
`collections` · `teams` · `players` (incluye IN/OUT y `together`) · `lineups` (REST + SSE `/stream`) · `scrape` (también en el servicio scraper) · `shots` · `possessions` · `reports` (informe semanal ZIP, PDF/DOCX, `export-pdf`, `individual-scouting/docx`) · `historical` · `analysis` + `analysis_predictive` (ambos bajo `/analysis`: ajuste por rival, elasticidades, Monte Carlo, backtesting, predicción) · `matches` · `multi_phase` (`/multi`) · `rotaciones` (REST + SSE). La API **no tiene autenticación** (el frontend protege `/admin` con `AuthContext`/`PrivateRoute`).

## Servicios (`src/services`)
- Stats: `team_stats_service`, `player_stats_service`, `evolution_service`, `match_analysis_service`, `multi_phase_service`, `lineup_service`, `rotation_service`, `rival_adjusted_service`, `collection_service`, `_consistency_calculator`.
- Predictivo (scikit-learn): `elasticity_service` (+`_elasticity_models`, `_ridge_helpers`, `_feature_builders`, `_gbm_models`), `monte_carlo_service`, `backtesting_service`, `game_prediction_service`, `player_prediction_service`, `season_projection_service`, `live_history_adapter`.
- Datos históricos: `historical_ingestion_service`, `_feb_normalizer`, `_fbcyl_normalizer`, `_historical_derived`.
- Informes/export: `report_service`, `weekly_report_service` (+`_weekly_report_helpers`), `individual_scouting_service` (+`_scouting_docx_helpers`, `_scouting_formatters`), `pdf_generator`, `possession_export_service`, `pbp_quality_service`, `player_data_fetcher`.

## Base de datos (`src/database`)
- `db_config.get_mongodb_connection_string()`: env `MONGODB_CONNECTION_STRING` → `src/database/db_credentials.txt` (no versionado) → valor por defecto. BD `BASKETBALL`, un `MongoDBHandler` (fachada) sobre `BasketballRepository` (+mixins `repository_games/_inout/_lineup/_possession`).
- Colecciones de partidos: `{competición}_{temporada}_{grupo}` saneado (`get_collection_name`); prefijo `FBCYL_` = formato FBCYL (`is_fbcyl`). Además `HISTORICAL` y `ELASTICITIES` (modelos entrenados).
- `aggregation/` (pipelines FEB y FBCYL), `indexes.py` (`IndexManager`, siempre `background=True`).
- Calculadoras PBP de BD: `inout_calculator`, `lineup_extractor`, `lineup_stats_calculator`, `possession_analyzer`.

## Frontend (`frontend/src`)
Vite + React + TS + TanStack Query + Tailwind + Recharts/D3; `api/client.ts` (todas las llamadas; `BASE` = `VITE_API_BASE`+`/api/v1`, scraper = `VITE_SCRAPER_BASE`), SSE con `EventSource` en lineups y rotaciones, `context/` (`CollectionContext`, `AuthContext`), `components/ui` (StatCard, FilterBar, DataTable, ExportButton…), `lib/` (utils, statLabels, exportDom). Rutas `/:collection/{teams,players,evolution,shots,rankings,report,possessions,inout,lineups,rotaciones,…}` y `/admin`. Proxy dev `/api` → `localhost:8000`.

## Despliegue y config
- `render.yaml`: `basketlab-api` (`python run_api.py`, `DISABLE_SCRAPING=1`) y `basketlab-scraper` (`python run_scraper.py`), plan free, Frankfurt. Frontend en Vercel (`vercel.json`: rewrite SPA). CI (`.github/workflows/ci.yml`): tests + deploy hook de Render en push a `main`.
- Env backend: `MONGODB_CONNECTION_STRING`, `ALLOWED_ORIGINS`, `ENVIRONMENT`, `DISABLE_SCRAPING`, `BASKETLAB_DEV`, `PORT`. Frontend: `VITE_API_BASE`, `VITE_SCRAPER_BASE`. Ejemplo en `.env.example`.

## Rutas de import duales y shims
Código y tests importan `src.x` y, a veces, `x` (con `src/` en `sys.path`). `src/database/playbyplay_core.py`, `src/database/_pbp_event_helpers.py` y `src/services/possession_core.py` son **shims** que reexportan `src/pbp/*` (mismos objetos; `tests/test_pbp_shims.py`). `tests/conftest.py` limpia cachés bajo ambos alias.

## Deuda conocida de arquitectura
Ver [ROADMAP.md](ROADMAP.md).
