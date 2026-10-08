# Motor de partido en vivo (para Claude)
Objetivo: durante un partido FEB, mostrar métricas y **alertas con propuestas** (quién entra por quién) en segundos. El motor es **biblioteca estándar** y corre en la tablet Android con **Pyodide**; BasketLab genera antes un *paquete de preparación* con la temporada. Formatos: [DATA_FORMATS.md](DATA_FORMATS.md).

## Piezas
- `src/pbp` (`event_helpers`, `playbyplay_core`, `possession_core`): parsers sin BD.
- `src/live_core` (stdlib; test de frontera con `pymongo/numpy/requests…` bloqueados):
  - Entrada: `clock` (periodos 4×600 s, prórrogas 300 s; FEB da tiempo **restante**), `events` (línea PBP → `Event`), `state` (`LiveGame`: marcador, faltas, tiros, rebotes ORB/DRB inferidos, minutos, **stint** con crédito de descanso —media parte reinicia, cuartos acreditan 60 s—, log `[elapsed, team, pts|tov|orb, v]`), `shots` + `zones` (zonas de tiro, familias), `engine` (`LiveEngine.update(doc)`: incremental, reconstruye si cambia el historial; reloj de la cabecera).
  - Análisis: `four_factors` (pesos de Oliver, encogimiento al prior, palanca principal, proyección), `profiles` (tasas por 40', roles inferidos por z-score, `impact40`), `recommender` (relevos de rol parecido y quinteto equilibrado), `rules_fouls`, `rules_team` (faltas/bonus/racha/pérdidas), `rules_rotation` (índice de fatiga), `rules_four_factors`, `rules_rival` (jugador rival "haciendo daño" y zonas), `advice` + `advice_types` (`AdviceEngine.evaluate/analyze`, dedupe y re-armado), `config` (`RuleConfig`: **todos** los umbrales).
  - Paquete y pruebas: `package` (`PreparationPackage`, JSON canónico + SHA-256 + versión), `replay` (`truncate_doc`, `ReplayClock`), `fake_feb` (servidor FEB simulado), `vectors` (ejecutor de vectores compartidos).
- `src/live_prep`: `package_builder` (reproduce los partidos con `LiveEngine`: mismas definiciones que en vivo), `db_source` (lee Mongo con proyección incl. `SHOTCHART.SHOTS`), `package_crypto` (AES-256-GCM + PBKDF2, compatible con WebCrypto).

## Datos
- **Snapshot** (`LiveEngine.update`): `period, remaining, elapsed, last_num, score{tid}, teams{tid:{name, fouls_game, fouls_by_period, timeouts, stats{fg2m…pts, tov, tov_team, orb, drb…}}}, players{pid:{name, team_id, on_court, minutes, stint, pf, pts, stats, stints_done, stint_sum}}, log, zones{tid:{zona:{a,m,pts}}}`.
- **Paquete**: `team, rival, tables{players, rival_players, zones{rival,league}, lineups[], roles[]}, baselines{four_factors_prior/sd, pace_per_40, league_rates, impact_league, sample_games}, rule_config, competition_meta`. Cifrado para subirlo a una carpeta de Drive compartida por enlace.
- **Alertas** (`Advice`: `key, id, severity, category, message (es), evidence, proposal[], rearm_s`). Reglas v1: faltas de jugador (aviso `min(periodo+1,3)`, 4 = crítica, nunca la 5ª), bonus de equipo, parcial rival 0-8 en 2:30, 4 pérdidas en 5', fatiga alta, palanca de Four Factors (≥3 pts/100), rival fuera de su ritmo (puntos, ORB, robos, asistencias, triples, TL), zonas del rival (eficiencia y volumen). Umbrales = placeholders **por confirmar** con el staff.

## Verificado
Estado, faltas por jugador, totales de equipo (tiros, ORB/DRB, pérdidas, robos, asistencias) y minutos coinciden con el box score oficial de la muestra; `SHOTCHART` = tiros del PBP; zonas idénticas al clasificador con shapely. **Pyodide 314 (Python 3.14) reproduce 320/320 vectores** de CPython 3.11; en un PC bajo Node: carga 1,5 s, importar 52 ms, actualización completa p50 20 ms / p95 26 ms (**no medido en tablet**).

## Pruebas
`tests/test_live_core_*.py`, `test_live_prep_*.py`; vectores: `tests/live_vectors/generate.py` → `vectors.json` (Python = referencia) y `tests/pyodide/run_vectors.mjs` (mismo ejecutor en Pyodide); CI `live-vectors.yml` regenera y exige `git diff` vacío. Tras cambiar `live_core`: regenerar vectores y revisar el diff.

## Límites y pendientes
- **Sin verificar con FEB real**: forma de `status/statusText` en directo, refresco de `BoxScore/KeyFacts/ShotChart`, vida del JWT, calendario de partidos futuros (hoy el scraper descarta partidos sin resultado).
- Parámetros placeholder: `ff_beta`, spreads, `n0`, pesos de fatiga. Sin datos de emparejamiento ni de quintetos (el recomendador mira jugadores sueltos). Rol inferido sin posición. 3 triples sobre la línea caen como de 2. Esquinas casi vacías (dato de origen).
- Decidido, **no implementado**: app Android independiente (Capacitor, motor en Web Worker con Pyodide, FEB vía HTTP nativa), paquete descargado de Drive con API key (cifrado), lista de partidos por equipo, modo local. Capas de prueba cloud previstas (Playwright/emulador/Firebase) en [TESTING.md](TESTING.md).
