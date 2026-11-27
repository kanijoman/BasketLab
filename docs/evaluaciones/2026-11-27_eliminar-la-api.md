# Eliminar la API (evaluación del 27/11/2026)

**Decisión (27/11/2026): se elimina**, en un próximo PR, épica #1199. La decisión #334 (05/11/2026) la mantuvo «para desarrollo y pruebas» y dejó su eliminación como decisión aparte: en desarrollo ya no se usa y producción nunca la tuvo alojada. Hasta que se integre ese PR, `src/api` y `run_api.py` siguen en el repositorio.

## Qué es «la API» aquí
- `src/api`: 22 módulos, 1.750 líneas (15 routers, `security`, `deps`, `memory`, `runtime`, `db_health`) y `run_api.py` (57 líneas).
- Ningún workflow la arranca. La web publicada lee `web-data` (local-first, #326) y el navegador ya tiene sus gemelos de PDF y DOCX (`jspdf`, `scoutingDocx.ts`, `scoutingPdf.ts`, `teamReportPdf.ts`).

## Qué depende de ella (medido el 27/11/2026)
| Qué | Tamaño |
|---|---|
| Tests que usan `src.api` o `TestClient` | 48 ficheros, 7.767 líneas, **24,6 % del tiempo de la suite** (1.217 de 4.939 s en `.test_durations`; ligado a #1110) |
| Web | el conmutador `?data=api` en 10 módulos de `frontend/src/api`, 32 tests `*Switch.test.ts`, `VITE_API_BASE` |
| E2E | `frontend/playwright.config.ts` arranca `tests/e2e_web/serve_api.py` (FastAPI real sobre Mongo en memoria) y el smoke prueba `/api/v1/health` |
| Scripts | `scripts/capture_forecast_fixtures.py` importa `src.api.deps._create_handler` |
| Dependencias | `fastapi`, `uvicorn` (y el `httpx` de `TestClient`) |
| Documentación | 11 ficheros (ARCHITECTURE, OPERATIONS, TESTING, DECISIONS, ROADMAP, CLAUDE.md, README…) |

## Qué se va con ella y qué no
- **Se va:** seis servicios solo alcanzables desde la API, ≈ 1.544 líneas con sus tests: `weekly_report_service`, `individual_scouting_service`, `pdf_generator`, `stats_calculator`, `match_derived`, `league_zones`. Se comprueba con el análisis de alcanzabilidad de importaciones (raíces: `run_*.py`, `scripts/`, `src/local_data`, `src/live_*`, `src/market`, `src/external` y los generadores de vectores).
- **No se toca (otra decisión, #641):** el oráculo Python de los vectores, ≈ 2.137 líneas que solo alcanzan la API y los generadores (`multi_phase_service`, `scouting_pdf`, `scouting_pdf_parts`, `scouting_docx_tables`, `_weekly_report_helpers`, `team_comparison_service`, `pbp_situation_stats_service`, `radar_chart`…). Quitarlo exige congelar los vectores como golden files y que TS sea canónico.
- **No se toca:** los servicios que usa la publicación de `web-data` (corren en CI): no son «de la API».

## Riesgos y cautelas
1. **Cobertura única**: parte de los 48 ficheros ejerce, vía `TestClient`, servicios que siguen vivos. Antes de borrar cada test, comprobar que su sujeto tiene otro test; si no, reescribirlo contra el servicio.
2. **E2E**: el smoke necesita otro origen de datos (fixtures estáticos de `web-data`), no solo quitar el servidor.
3. **Escrituras**: `ADMIN_API_KEY` y el patrón de `require_admin` (hoy sin rutas, #724) pasan al archivo histórico; el día que haya escrituras, se decidirá con el modelo de acceso (#591).

## Plan (un PR, un commit por issue, en este orden)
1. #1200 Web: quitar `?data=api`, `VITE_API_BASE` y los conmutadores.
2. #1201 E2E y fixtures sin FastAPI.
3. #1202 Borrar `src/api`, `run_api.py`, `fastapi`/`uvicorn`, tras auditar la cobertura única.
4. #1203 Borrar los servicios huérfanos.
5. #1204 Docs: sustituir #334 y retirar la API de la documentación.

Efecto esperado: ≈ −25 % del tiempo de la suite (#1110), ≈ 3.300 líneas de producción y 7.700 de tests menos, dos dependencias menos y un solo modo de datos en la web.
