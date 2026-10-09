# Hoja de ruta, deuda y límites (para Claude)
Actualizar al cerrar cada entrega (regla de [CLAUDE.md](../CLAUDE.md)). Estado detallado del motor live: [LIVE.md](LIVE.md).

## Hecho
| Área | Qué | Dónde |
|---|---|---|
| Limpieza | capa de escritorio PyQt eliminada (FASE 0); LLMs externos eliminados | — |
| Predictivo | ajuste por rival · elasticidades Ridge (modelos A/B) · Monte Carlo · backtesting walk-forward · clasificador victoria/derrota (logística + Platt) · predicción por jugador · proyección de clasificación | `src/services/*_service.py`, `analysis*.py` |
| Informes | informe semanal (ZIP de PNG), scouting individual DOCX (sin IA), export PDF, **informe de equipo por reglas** (propio/rival, JSON+PDF, página `team-report`) | `reports.py`, `team_report.py`, `src/report_engine`, `weekly_report_service`, `individual_scouting_service` |
| Live (motor) | estado incremental, alertas, Four Factors, recomendador, alertas del rival (jugador y zonas), paquete cifrado, vectores Python↔Pyodide | `src/live_core`, `src/live_prep` |
| Calidad | guarda de ingesta de partidos en curso, extracción de `src/pbp`, tests de docs | — |
| Datos y operaciones | refresco programado de Atlas desde FEB con informe de frescura (#177), diagnóstico de BD (`/health/db`), grabador del feed en directo (#171), paquetes de los próximos partidos publicados en la rama `live-packages` (#175) | `.github/workflows/atlas-refresh.yml`, `feb-record.yml`, `live-packages.yml` |
| Calidad web | smoke e2e Playwright en CI (requisito del deploy) y comprobación post-despliegue de la API (#111) | `frontend/e2e`, `scripts/post_deploy_check.py` |
| UI | tabla de posesiones en 3 vistas con columna de equipo con logo (#183), arreglos de recientes/COLLECTION_META/IN-OUT (#181) | `frontend/src/pages/possessions` |

## Pendiente
1. **Live con datos reales** (bloqueante): capturar un partido en directo (`status`, refresco, JWT, `ShotChart`) y el HTML del calendario; calibrar umbrales con el staff.
2. Lista de partidos por equipo (#119) hecha para competiciones de un grupo; pendiente multi-grupo y confirmar con un partido real cómo se ve uno en juego (#118).
3. **App Android** (#120, `apps/live-android`): esqueleto hecho (motor en Web Worker con Pyodide, modo demo, CI con e2e y APK, release por etiqueta). Paquete de extremo a extremo hecho (#133: generar en la web, importar en la app) y automático (#175: publicado en la rama `live-packages` y descargable en la app; sin Drive, #162 descartado). Pendiente: fuente real FEB (#118/#119), prueba en tablet real (versión mínima de WebView, fluidez medida en dispositivo).
4. Informes por reglas v1 completa (épica #145: zonas vs liga en FEB y FBCYL, sin mínimo de partidos, PDF sin cortes de fila). v2 diferida (#146).
5. **Modelos live**: evaluar win-prob/proyección con *replay* de histórico (Brier, MAE) antes de enseñar probabilidades; calibrar `ff_beta`, spreads y `n0`.
6. Optimizador de quintetos, proyección multi-temporada de jugador (ideas antiguas, sin empezar).
7. **Rework de UI** (épica #187, en backlog): sistema de diseño con tokens y tema claro/oscuro, marca nueva, componentes base, `TeamCell`/DataTable (#184), shell móvil y migración de todas las páginas. Detalle y fases en el issue; se arranca con U0 (#188).

## Deuda técnica (>500 líneas; dividir al tocarlos)
Python: `database/aggregation/fbcyl_pipeline.py` 1322 · `pipeline_team_stats.py` 949 · `scraper/feb_scraper.py` 800 · `shotcharts/court_zones.py` 772 · `services/rotation_service.py` 722 · `_weekly_report_helpers.py` 660 · `stats/advanced_stats_calculator.py` 632 · `shotcharts/detailed_zones.py` 629 · `database/inout_calculator.py` 613 · `lineup_stats_calculator.py` 609 · `shot_visualizer.py` 596 · `repository_inout.py` 595 · `pbp/possession_core.py` 592 · `fiba_court.py` 579 · `weekly_report_service.py` 557 · `fbcyl_scraper.py` 542 · `pipeline_player_stats.py` 505.
Frontend: `PredictivePage.tsx` 1419 · `api/client.ts` 1321 · `AdminPage.tsx` 703 · `PlayerStatsPage.tsx` 674 · `LineupsPage.tsx` 653 · `RotacionesPage.tsx` 624.
Otros: la API solo tiene una clave de administración (sin usuarios/roles ni protección de lecturas; #115) · en BDs ya creadas queda el índice antiguo `header_local_team_name_1` (inofensivo; `drop_index` si se quiere limpiar).

## Límites conocidos
Esquinas casi vacías en el sistema de 10 zonas (dato de origen) · live solo FEB (FBCYL tiene minutos con precisión de 1 min y tiempo transcurrido) · colecciones pequeñas dan líneas base ruidosas (todo se encoge hacia la media de liga) · sin emparejamientos jugador-vs-jugador. El scouting individual (DOCX) sigue sin perfil de tiro en FBCYL (solo FEB).

## Backlog
Fuente única: **GitHub Issues** (`gh issue list`). Aquí no se duplica; solo contexto estratégico. Etiquetas: `bug`, `enhancement`, `tech-debt`, `testing`, `live`.
