# Historia de ARCHITECTURE.md

Pasajes de [ARCHITECTURE.md](../ARCHITECTURE.md) que cuentan qué se retiró o cómo era antes (movidos tal cual el 27/11/2026); el documento solo dice lo que es cierto hoy.

## Routers: endpoints retirados en #202

; **retirados en #202 los endpoints sin ningún cliente** —el router `live` entero (`/live/matches`, `/live/package`: los paquetes los publica Actions y la app los baja de `live-packages`), `export-pdf`, `player-scouting`, `team-scouting`, `season-summary`, los `breakdown` de `/multi` y `collections/{name}/freshness`—

## Servicios: predictivo antiguo retirado del servidor (#853)

**El predictivo antiguo se retiró del servidor (#853)**: sin `elasticity_service`, `monte_carlo_service`, `backtesting_service`, `game_prediction_service`, `player_prediction_service`, `season_projection_service`, `live_history_adapter` (ni scikit-learn en `requirements.txt`: lo que lo necesita, los estudios de `scripts/`, está en `requirements-research.txt`). La previa y la simulación se calculan en el navegador (`frontend/src/forecast/`, ver más abajo) sobre `web-data`.

## Servicios: datos históricos (#853)

la ingesta a `HISTORICAL` (`historical_ingestion_service`, los normalizadores y `_historical_derived`) se retiró con el predictivo antiguo (#853). 

## Frontend: página Administración (#724) y predictivo antiguo (#852) retirados

(**la página Administración se retiró, #724**: sin ruta —`/admin` redirige al inicio—, sin enlace en la barra lateral ni en el inicio, y sin las llamadas de `api/client.ts` a `scrape/*`, `historical/ingest*` y `DELETE collections`; **el predictivo antiguo se retiró en #852**: sin `pages/predictive/`, `PredictivePage`, `ModelsTab` ni `api/predictive.ts` (Ridge, Monte Carlo por estadística, predicción por jugador, validación), y `/predictive` redirige a «Previa del partido», que lo sustituye; `getRivalAdjusted` y `getLiveTeamNames` viven ahora en `api/teams.ts` y `api/collections.ts`)

## Frontend `localdata/`: tabla de jugadores de FBCYL (#644)

(la API repetía la tabla propia como rival hasta #642, y su contexto de las cifras avanzadas con ella)

## Frontend `datasource/`: conjunto `evolution` (#708)

, y arregla de paso `won` de FBCYL en el API, que leía un `isWinner` que ningún documento real trae y devolvía siempre «no ganado»

## Frontend `datasource/`: conjunto `team-stats` (#706)

; arregla de paso el endpoint para FBCYL, que listaba `teams.name` y devolvía siempre `[]`

## `src/market`: `profile` y `eligible` (#1010)

; antes bastaban 5 minutos en toda la temporada y lo cumplía el 94,6 % de las filas senior de FEB (medido el 20/11/2026: ahora el 69,6 %)

## `src/local_data`: imágenes (`images_export`, #1085)

; medido el 25/11/2026, leerlas en cada publicación costaba de 4 a 9 minutos más de un Web data de ≈ 25–28
