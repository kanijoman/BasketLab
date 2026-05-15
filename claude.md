# Claude AI Development Context - BasketLab

## Project Identity
**BasketLab** - PyQt6 basketball statistics analyzer (Spanish leagues: FEB/FBCYL). MongoDB + matplotlib + multi-provider AI. PoC phase (LF2).
**Stack:** Python 3.8+ | PyQt6 | MongoDB | matplotlib | fpdf2 | python-docx | Gemini/OpenAI/Groq

## ❌ TDD ES OBLIGATORIO — NUNCA SALTAR ESTE PASO

> **Si modificas código sin haber escrito antes el test que falla → PARA. Escribe el test primero.**

**Ciclo rojo→verde (sin excepciones, incluye bugfixes):**
1. `tests/test_<feature>.py` — escribir test que describe el comportamiento deseado
2. `pytest -v tests/test_<feature>.py` — confirmar que **falla** (rojo)
3. Implementar el mínimo código que lo corrija
4. `pytest -v tests/test_<feature>.py` — confirmar que **pasa** (verde)
5. Ningún PR / commit sin este ciclo completado

**Violaciones frecuentes a evitar:**
- Arreglar un bug directamente sin test de regresión previo
- Añadir un feature y los tests después
- "Es un fix pequeño, no necesita test" → **No existe fix pequeño sin test**

---

## Your Role as Claude

**Implementation rules:**
- **Infer > ask**: "add export" = CSV/PNG/PDF trinity (standard)
- **Follow patterns**: Search similar code before creating new
- **Dual format**: Always handle FEB + FBCYL (`is_fbcyl` flag)
- **Code English, UI Spanish**: All code/comments in English; UI strings in Spanish
- **Search tools**: `grep_search` for patterns, `semantic_search` for similar code, parallel file reads

**Pre-completion check (MANDATORY every 100 lines written):**
1. **File size check**: Current lines >300? → Extract module/helper NOW (don't wait for 500)
2. **Function length**: Any function >40 lines? → Split immediately before continuing
3. **Duplication scan**: `grep_search` for similar patterns → Reuse/extend existing code
4. **Complexity audit**: Nesting >3 levels or >5 conditionals? → Refactor before proceeding
5. **Pattern compliance**: Using StatsCalculator/Repository/helpers? Check imports match project patterns

**Ask clarification only for:**
- Missing business logic thresholds
- Ambiguous feature scope
- UI layout preferences

**Testing (mandatory after features):**
1. Design test plan (happy path + edge cases + errors)
2. Execute tests, verify no exceptions
3. Run full test suite if available (prevent regressions)
4. Checklist: [ ] No exceptions [ ] Edge cases (empty/None/zero) [ ] FEB+FBCYL tested [ ] UI responsive (QThread) [ ] No regressions

**Bug fixes → regression test (mandatory):**
Every bug fix must be accompanied by a test that:
- Reproduces the exact failure condition (name it `test_<symptom>_regression` or document the bug in the docstring)
- Passes only after the fix is applied
- Lives in `tests/` and is included in the same commit as the fix
No fix is complete without its regression test.

**Code reuse (check before writing):**
- **Use libraries**: scipy/numpy/pandas for stats, requests for HTTP (don't reinvent)
- **Scan codebase**: Use `grep_search`/`semantic_search` before creating functions
- **Adapt > duplicate**: If 80% match exists, extend it (e.g., add params to `calculate_team_efficiency()`)
- **Check utils**: [stats_calculator.py](src/ui/stats_calculator.py), [database/utils.py](src/database/utils.py), [ui_utils.py](src/ui/ui_utils.py)
- **DRY**: Repeated logic → shared function; similar tables → extend `StatsTableManager`

**Refactoring (analyze after mods):**
- **File size**: >500 lines → propose split into modules
- **Complexity**: >3 nesting levels, >5 if/elif, >50 line functions → refactor
- Flag issues: "File X: 650 lines, extract Y" | "Function Z: complexity ~12, split needed"

## Architecture
- **UI → Repository → MongoDB**: Never direct DB access from frontend
- **Web stack**: FastAPI (port 8000) + React/Vite (port 5173)
- **Complex queries**: Aggregation pipelines (NOT Python filtering)
- **AI flow**: Stats → `ContextBuilder` → `TeamAnalyzer` (multi-provider)
- **Viz**: matplotlib → PNG bytes returned by API

## Mandatory Patterns

### FastAPI / Python backend

```python
@router.get("/example/{collection}")
def get_example(collection: str, db: MongoDBHandler = Depends(get_db)):
    svc = MyService(db)
    return svc.get_data(collection)
```
**Background ops:** Use FastAPI `BackgroundTasks` — never block the event loop
**Lazy imports in services:** Use `from src.services.xxx import X` inside functions for optional heavy deps

### MongoDB
**NEVER:** `list(collection.find({}))` then filter in Python
**DO:** Filter in DB: `collection.find({"field": value})`
**Complex queries:** Use `AggregationPipelineBuilder` (NOT Python post-processing)
**Indexes:** Always `background=True`, update `IndexManager` for new query fields

### Dual Data Format (FEB vs FBCYL)
**Always check `is_fbcyl`:**
- FEB: `doc["HEADER"]["localTeam"]["teamName"]`, `doc["BOXSCORE"]["TEAM"][0]["PLAYER"][0]["points"]`
- FBCYL: `doc["stats"]["teams"][0]["name"]`, `doc["stats"]["teams"][0]["players"][0]["PTS"]`
- Field map: `points`/`PTS`, `totalRebounds`/`REB`, `assists`/`AST`, `minutes` ("MM:SS")/`MIN` (float), `license`/`uuid`

### Quartiles, Export, Possessions
- **Quartiles**: `StatsTableManager.apply_quartile_coloring(table, col_idx, values, reverse=False)` | Q1=green, Q4=red | reverse=True for TOV/fouls
- **Export**: Every window needs `StatsExporter(self, table, "filename")` → auto CSV/PNG/PDF
- **Possessions**: `FGA - ORB + TOV + 0.44*FTA` | Normalize: `(stat/possessions)*40` (always 40min baseline)

## Code Navigation

**Add new features:**
| Task | Location | Related |
|------|----------|----------|
| Stats window | [src/ui/](src/ui/) new file | [stats_table_manager.py](src/ui/stats_table_manager.py), [stats_exporter.py](src/ui/stats_exporter.py) |
| Stats calc | [stats_calculator.py](src/ui/stats_calculator.py) | [stats_config.py](src/ui/stats_config.py) |
| DB query | [repository.py](src/database/repository.py) | [aggregation/](src/database/aggregation/) |
| Pipeline | [pipeline_builder.py](src/database/aggregation/pipeline_builder.py) | [advanced_stats.py](src/database/aggregation/advanced_stats.py) |
| AI analysis | [prompts.py](src/ai/prompts.py) | [context_builder.py](src/ai/context_builder.py) |
| Shot chart | [shot_visualizer.py](src/shotcharts/shot_visualizer.py) | [zone_analysis.py](src/shotcharts/zone_analysis.py) |
| Scraper | [src/scraper/](src/scraper/) new file | [api_client.py](src/scraper/api_client.py), [web_client.py](src/scraper/web_client.py) |

**Entry points:** [main.py](src/main.py) | [main_window.py](src/ui/main_window.py) | [connection.py](src/database/connection.py) | [repository.py](src/database/repository.py) | [stats_config.py](src/ui/stats_config.py)

## Implementation Templates

**MongoDB Pipeline:**
```python
def build_custom_pipeline(team_id, is_fbcyl=False):
    if not is_fbcyl:
        return [{"$match": {"$or": [{"HEADER.localTeam.teamId": team_id}, {"HEADER.visitorTeam.teamId": team_id}]}},
                {"$project": {"teamName": {"$cond": [...]}, "points": {"$cond": [...]}}},
                {"$group": {"_id": "$teamName", "totalPoints": {"$sum": "$points"}}}]
    else:
        return [{"$match": {"stats.teams.id": team_id}}, {"$unwind": "$stats.teams"}, 
                {"$match": {"stats.teams.id": team_id}}, {"$group": {...}}]
```

**Table + Quartiles:**
```python
def populate_table(self, data):
    points_vals = [t["points"] for t in data]
    for row, team in enumerate(data):
        self.table.setItem(row, 0, QTableWidgetItem(team["name"]))
        self.table.setItem(row, 1, NumericTableWidgetItem(team["points"]))
    StatsTableManager.apply_quartile_coloring(self.table, 1, points_vals, reverse=False)
```

**AI Analysis:**
```python
from src.ai.team_analyzer import TeamAnalyzer
from src.ai.context_builder import ContextBuilder
from src.ai.config import AnalysisConfig

formatted = ContextBuilder.format_team_statistics(stats, quartiles, is_comparative=False)
config = AnalysisConfig(); config.load_api_keys()
analyzer = TeamAnalyzer(config)
analysis = analyzer.analyze_team("Team", formatted, "own", provider="groq")
```

**Trends:** `TrendCalculator.calculate_trend(recent, season, reverse=False)` → ⇈(>10%) ↑(5-10%) ≈(<5%) ↓(5-10%) ⇊(>10%)

## Common Pitfalls

| ❌ Don't | ✅ Do |
|---------|--------|
| `doc["BOXSCORE"]["TEAM"][0]["PLAYER"][0]["points"]` (assumes FEB) | Check `is_fbcyl`: FEB=`points`, FBCYL=`PTS` |
| `collection.create_index("field")` (blocks DB) | `collection.create_index("field", background=True)` |
| `QTableWidgetItem(str(10.5))` (wrong sort) | `NumericTableWidgetItem(10.5)` |
| `import openai; openai.ChatCompletion.create(...)` (vendor lock) | `TeamAnalyzer(config).analyze_team(..., provider="groq")` |
| `config_path = "src/database/db_credentials.txt"` (hardcoded) | `config = find_db_config()` (env → local → packaged) |
| `self.setWindowTitle("Team Statistics")` | `self.setWindowTitle("Estadísticas de Equipo")` (Spanish UI) |

## Decisions Already Made (Don't Re-debate)
- **PyQt6** (not PyQt5): Modern, future-proof | **MongoDB** (not SQL): JSON-native, flexible
- **Aggregation pipelines** (not ORM): Performance | **fpdf2** (not WeasyPrint/ReportLab): HTML support, lightweight
- **Multi-provider AI** (not single): No lock-in | **Matplotlib** (not Plotly): FIBA precision
- **pymongo** (not motor): Sync fits PyQt | **python-docx**: Native DOCX

## Business Logic

**Quartiles (MongoDB 7.0+):** `{"$group": {"_id": null, "q1": {"$percentile": {"input": "$metric", "p": [0.25], "method": "approximate"}}}}`

**Trends:** ⇈ >10% (green #006400) | ↑ 5-10% (#28a745) | ≈ <5% (gray #6c757d) | ↓ 5-10% (orange #fd7e14) | ⇊ >10% (red #dc3545)

**Possessions:** `FGA - ORB + TOV + 0.44*FTA`

**Four Factors:** eFG%=`(FGM+0.5*3PM)/FGA` | TOV%=`TOV/(FGA+0.44*FTA+TOV)` | ORB%=`ORB/(ORB+opp_DRB)` | FTr=`FTA/FGA`

**Shot Zones (10):** Restricted (0-1.25m), Paint (0-4m non-restricted), Mid-range (L/C/R), 3PT (corner L/R, wing L/R, top)

## Update This File When
- Major architecture changes (DB migration, framework change)
- New mandatory patterns (UI standards, data handling)
- Module additions (new `/src/` directories)
- Breaking dependency changes (PyQt6→PyQt7)
- New data sources (ACB league, different schemas)
**How:** Announce "updating claude.md", use `replace_string_in_file`, keep <400 lines

## Commands
```bash
.\install_dependencies.ps1        # Install deps
.\build_windows.ps1               # Build EXE
python src/main.py                # Run dev (PyQt6)
python run_api.py                 # Run FastAPI backend (:8000)
cd frontend && npm run dev        # Run Vite frontend (:5173)
# DB creds: src/database/db_credentials.txt (format: mongodb+srv://user:pass@cluster/db)
# AI keys: ~/.basketlab/config.txt
```

## Predictive Analytics Roadmap (Descriptivo → Predictivo)

### ✅ COMPLETADO
| Fase | Descripción | Archivos clave | Tests |
|------|-------------|----------------|-------|
| FASE 0 | Eliminar capa Qt UI deprecada | `src/ui/` → eliminado, `src/utils/team_utils.py`, `src/services/pdf_generator.py`, `src/services/player_data_fetcher.py` | - |
| FASE 2 | Rival-adjusted stats | `analysis.py` /rival_adjusted | - |
| FASE 3/4 | Elasticity Ridge models (Modelo A/B) | `elasticity_service.py` | `test_elasticity_*` |
| FASE 5 | Monte Carlo team projection | `monte_carlo_service.py` | `test_monte_carlo_*` |
| FASE 6 | Walk-forward backtesting | `backtesting_service.py` | `test_backtesting.py` (16) |
| FASE 7 | Win/Loss classifier (Logistic+Platt) | `game_prediction_service.py` | `test_game_prediction.py` (22) |
| FASE 8 | Player-level Ridge prediction | `player_prediction_service.py` | `test_player_prediction.py` (21) |
| FASE 9 | Season-end standings projection MC | `season_projection_service.py` | `test_season_projection.py` (21) |
| FASE 11 | Refactor deuda técnica | `repository_inout.py`, `elasticity_service.py`, `analysis.py`, `player_prediction_service.py` split | - |
| FASE D | individual_scouting_service split | `_scouting_docx_helpers.py`, `_scouting_formatters.py` | `test_individual_scouting.py` (22) |
| FASE A | Backend coverage crítica | `test_indexes.py` (12), `test_scraper_endpoints.py` (18), `test_individual_scouting.py` (22), `test_weekly_report.py` (14) | 66 |
| FASE B | Weekly report helpers coverage | `test_weekly_report_helpers.py` — `_cv_badge_color`, `apply_cv_overlay`, `render_table_png`, `q_color`, `calc_quartiles`, CV formula regression | 43 |
| FASE C | PlayerStatsService CV + phantom guard | `test_player_stats_cv_regression.py` — FEB/FBCYL CV formula (near-zero floor, 200% cap), FIELD_MAP regression, `_player_minutes_played` phantom logic | 29 |

**Suite total: 773 tests, 0 failures (HEAD `5b4a89a`)**

### 🔜 PRÓXIMAS FASES PROPUESTAS

**FASE 10 — Prescriptive Automation (Recomendador táctico)**
- Input: equipo + próximo rival → output: recomendaciones de ajuste
- `prescriptive_service.py`: usa ElasticityService + GamePredictionService
- Endpoint: `POST /api/v1/analysis/prescriptive/{team_id}`
- UI: tab "Recomendaciones" en PredictivePage
- Complejidad: Media | Impacto: Alto

**FASE 11 — Refactor de servicios grandes (deuda técnica)**
- `analysis.py` (409L) → split en `routers/analysis_predictive.py` + `routers/analysis_player.py`
- `player_prediction_service.py` (357L) → extraer `_ridge_helpers.py`
- `elasticity_service.py` (480L) → extraer `_elasticity_models.py`
- `repository_inout.py` (1001L) → URGENTE split en módulos
- Complejidad: Media | Impacto: Calidad

**FASE 12 — Player Scouting Predictive**
- Proyección de próximas N temporadas para un jugador (Ridge multi-temporada)
- Curvas de desarrollo por edad (polynomial regression)
- `player_development_service.py` usando HISTORICAL
- Endpoint: `GET /api/v1/analysis/player-development/{player_id}`
- Complejidad: Alta | Impacto: Alto

**FASE 13 — Lineup Optimizer (Prescriptivo avanzado)**
- Dado un rival, recomendar el quinteto con mayor P(victoria)
- GamePredictionService por combinación de quinteto
- `lineup_optimizer_service.py`: pruning por combinatoria (máx 5-choose-5 de 12)
- Endpoint: `POST /api/v1/analysis/lineup-optimizer/{collection}`
- Complejidad: Alta | Impacto: Muy Alto

**FASE 14 — Live Dashboard (tiempo real)**
- WebSocket endpoint para live-update durante partidos
- Actualización automática de net_rtg parcial → recalcular predicciones
- `ws/live/{collection}/{match_id}`
- Complejidad: Muy Alta | Impacto: Diferenciador

### Deuda técnica identificada
| Archivo | Líneas | Acción recomendada |
|---------|--------|-------------------|
| `repository_inout.py` | ~595 | Already split in FASE 11 — monitor growth |
| `individual_scouting_service.py` | 637 | Extract helpers |
| `historical_ingestion_service.py` | 628 | Extract pipeline builders |
| `team_stats_service.py` | 580 | Extract calculators |
| `possession_analyzer.py` | 574 | Extract zone helpers |

---
*AI-only doc. Human docs: [README.md](README.md), [DATABASE_CONFIG.md](DATABASE_CONFIG.md), [DISTRIBUTION_GUIDE.md](DISTRIBUTION_GUIDE.md)*
