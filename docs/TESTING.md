# Testing (para Claude)
Regla de trabajo (TDD, regresión por bug): [CLAUDE.md](../CLAUDE.md). Este doc: cómo se prueba, qué hay y qué falta.

## Ejecutar
```bash
pytest -q                                   # backend completo (cobertura sobre src/ por defecto, pytest.ini)
pytest tests/test_live_core_*.py -q --no-cov
cd frontend && npm run lint && npm run type-check && npm run test:run && npm run build
python tests/live_vectors/generate.py       # regenerar vectores live tras cambiar live_core
cd tests/pyodide && npm ci && node run_vectors.mjs   # motor dentro de Pyodide
```
Dependencias: `pip install -r requirements-dev.txt` (Render usa solo `requirements.txt`). Tests con marker `ml` (`test_backtesting`, `test_game_prediction`, `test_player_prediction`, `test_predictive`, 2 de `test_regression_formulas`) se **saltan** solos sin `scikit-learn`; en CI corren. Frontend en Windows: si vitest no arranca por el binding de rolldown, `rm -rf frontend/node_modules && npm ci`.

## Mapa de tests (≈ 95 archivos, 1.986 tests backend, cobertura 72 %; frontend 9 archivos / 68 tests)
- API (`TestClient`, `dependency_overrides[get_db]`): `test_api*.py`, `test_*_router.py`, `test_integration_api_services.py`, `test_lineups_sse.py`, `test_scraper_endpoints.py`.
- Servicios y BD con `mongomock` (sin red ni Mongo real): `test_services.py`, `test_rotation_service.py`, `test_repository_*`, `test_pipeline_builder.py`, `test_indexes.py`.
- PBP/posesiones: `test_possession_*`, `test_playbyplay_analyzer.py`, `test_pbp_*`. Predictivo (necesita sklearn): ver arriba. Informes/export: `test_pdf_generator.py`, `test_weekly_report*`, `test_individual_scouting.py`.
- Live: `test_live_core_*`, `test_live_prep_*`, `test_live_vectors.py`, `test_live_pyodide.py` (salta sin Node), frontera de imports sin BD (`test_live_core_boundary.py`).
- Guardas: `test_no_llm_dependencies.py`, `test_no_hardcoded_secrets.py`, **`test_docs_consistency.py`** (docs sincronizados con el código).
- Fixtures: `tests/conftest.py` (`feb_game_doc`, `fbcyl_game_doc`, `mock_*_db`; limpia cachés bajo ambos alias de import), `tests/live_helpers.py`.

## CI (`.github/workflows`)
`ci.yml`: backend (`pytest --cov --cov-fail-under=70`, Python 3.11, instala `requirements-dev.txt`; subir el umbral cuando la cobertura mejore), frontend (`npm ci`, lint, type-check, vitest, `npm run build`), deploy a Render solo en push a `main`. `live-vectors.yml`: regenera vectores (falla si `git diff`), pruebas de referencia sin `conftest`, vectores en Pyodide.

## Evaluación (estado actual) y mejoras
| Hueco | Prioridad | Estado |
|---|---|---|
| Tests de ML y deps de test mezcladas con runtime | alta | **hecho** (marker `ml`, `requirements-dev.txt`) |
| Sin `vite build` ni gate de cobertura en CI | alta | **hecho** (build + `--cov-fail-under=70`, base 72 %) |
| Router `rotaciones` sin test; `analysis_predictive` | alta | **hecho** (`test_rotaciones_router.py`; predictive ya estaba cubierto) |
| `fetch` crudo en páginas ignoraba `VITE_API_BASE`; `getPlayerRankings/Radar` a rutas inexistentes | media | **hecho** (todo vía `client.ts`; `client.test.ts`) |
| Frontend: sin tests de páginas ni del SSE de `client.ts` | media | pendiente (bajo retorno; preferir smoke e2e) |
| Sin **contrato** back↔front (0 `response_model`; tipos TS a mano) | media (más trabajo) | hoja de ruta: modelos Pydantic + OpenAPI → tipos TS |
| Sin e2e ni smoke contra servidor real; sin health-check post-deploy | media | hoja de ruta: Playwright contra uvicorn + build |
| `npm run lint` roto (no había config) | baja | **hecho** (`eslint.config.js`, en CI: errores fallan, 6 avisos pendientes → B7) |
| `mongomock.MongoClient()` ad hoc en ~20 tests pudiendo usar fixtures | baja | — |
Frontend: compensa testear `client.ts` y helpers puros; testear páginas enteras con mocks rinde poco (mejor un smoke e2e).

## Marco cloud para la app Android (previsto)
Capas gratuitas en GitHub Actions/Google: pytest del motor → motor en Pyodide (hecho) → UI en perfiles Android de Playwright con FEB y Drive simulados (`fake_feb`) → APK en emulador con Maestro → Firebase Test Lab → App Distribution. Fluidez: motor en Web Worker; con reproducción ×30 y CPU ×4 más lenta contar tareas largas del hilo principal. Canario diario contra un partido FEB finalizado.

## Checklist manual (rescatado del plan antiguo)
Con API y frontend arrancados (Swagger en `localhost:8000/docs`): `GET /api/v1/historical/summary` con datos · `rival_adjusted` en una colección FEB y otra FBCYL (`adj_avg = raw_avg + adj`) · `elasticity/train` (422 sin datos; 12 modelos con datos) y `predict` (IC coherente; 404 equipo inexistente) · `montecarlo/<team>` (`n_games` ≤ 10 y `n_simulations` ≥ 100, si no 422; `win_prob` en [0,1]) · regresión: `GET /`, `teams/<col>/stats`, `players/<col>/stats`, `collections/list` · casos: FEB y FBCYL, equipo con < 10 partidos (error controlado), Mongo caído (error gestionado, no 500) · descargar en `Informes`: ZIP semanal y DOCX de scouting individual.
