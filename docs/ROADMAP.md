# Hoja de ruta, deuda y límites (para Claude)
Actualizar al cerrar cada entrega (regla de [CLAUDE.md](../CLAUDE.md)). Estado detallado del motor live: [LIVE.md](LIVE.md).

## Hecho
| Área | Qué | Dónde |
|---|---|---|
| Limpieza | capa de escritorio PyQt eliminada (FASE 0); LLMs externos eliminados | — |
| Predictivo | ajuste por rival · elasticidades Ridge (modelos A/B) · Monte Carlo · backtesting walk-forward · clasificador victoria/derrota (logística + Platt) · predicción por jugador · proyección de clasificación | `src/services/*_service.py`, `analysis*.py` |
| Informes | informe semanal (ZIP de PNG), scouting individual DOCX (sin IA), export PDF | `reports.py`, `weekly_report_service`, `individual_scouting_service` |
| Live (motor) | estado incremental, alertas, Four Factors, recomendador, alertas del rival (jugador y zonas), paquete cifrado, vectores Python↔Pyodide | `src/live_core`, `src/live_prep` |
| Calidad | guarda de ingesta de partidos en curso, extracción de `src/pbp`, tests de docs | — |

## Pendiente
1. **Live con datos reales** (bloqueante): capturar un partido en directo (`status`, refresco, JWT, `ShotChart`) y el HTML del calendario; calibrar umbrales con el staff.
2. **Lista de partidos por equipo** (próximos/en curso): parser de calendario sin descartar `*-*`, metadatos de competición por colección (`competition_url`, `season_value`, `group_value`, `year`).
3. **App Android independiente** (`apps/live-android/`, Capacitor): motor en Web Worker con Pyodide, FEB por HTTP nativa, paquete desde Drive (cifrado, API key de solo lectura). Probar Pyodide en una tablet real; versión mínima de Android/WebView.
4. **Motor de informes por reglas** (sustituye al análisis LLM): registro de reglas sobre stats/cuartiles/consistencia → hallazgos con evidencia → plantillas → PDF/DOCX (`PDFGenerator`, `export-pdf`), reutilizando el patrón `Advice`/`RuleContext` de `live_core`. Debe cubrir "propio equipo" y "scouting rival" que tenía la página de IA.
5. **Modelos live**: evaluar win-prob/proyección con *replay* de histórico (Brier, MAE) antes de enseñar probabilidades; calibrar `ff_beta`, spreads y `n0`.
6. Optimizador de quintetos, proyección multi-temporada de jugador (ideas antiguas, sin empezar).

## Deuda técnica (>500 líneas; dividir al tocarlos)
Python: `database/aggregation/fbcyl_pipeline.py` 1322 · `pipeline_team_stats.py` 949 · `scraper/feb_scraper.py` 800 · `shotcharts/court_zones.py` 772 · `services/rotation_service.py` 722 · `_weekly_report_helpers.py` 660 · `stats/advanced_stats_calculator.py` 632 · `shotcharts/detailed_zones.py` 629 · `database/inout_calculator.py` 613 · `lineup_stats_calculator.py` 609 · `shot_visualizer.py` 596 · `repository_inout.py` 595 · `pbp/possession_core.py` 592 · `fiba_court.py` 579 · `weekly_report_service.py` 557 · `fbcyl_scraper.py` 542 · `pipeline_player_stats.py` 505.
Frontend: `PredictivePage.tsx` 1419 · `api/client.ts` 1321 · `AdminPage.tsx` 703 · `PlayerStatsPage.tsx` 674 · `LineupsPage.tsx` 653 · `RotacionesPage.tsx` 624.
Otros: `database/indexes.py` indexa `HEADER.localTeam.teamName` (campo inexistente en FEB) · `datetime.utcnow()` obsoleto en `historical_ingestion_service` y `elasticity_service` · shims de `src/pbp` retirables cuando no queden importadores antiguos · la API no tiene autenticación.

## Límites conocidos
Esquinas casi vacías en el sistema de 10 zonas (dato de origen) · live solo FEB (FBCYL tiene minutos con precisión de 1 min y tiempo transcurrido) · colecciones pequeñas dan líneas base ruidosas (todo se encoge hacia la media de liga) · sin emparejamientos jugador-vs-jugador.
