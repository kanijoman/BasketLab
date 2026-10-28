# Biblioteca de partidos raros (#546, B3 de #540)

Partidos **reales** con una rareza que el motor llegó a tratar mal. Cada incidente nuevo del staff aporta uno: así el siguiente arreglo se prueba contra datos de verdad, no solo contra estados inventados.

- `index.json` es el catálogo: por partido, qué tiene de raro, de qué incidente viene y la **sonda** (`probe`) que mide esa rareza (`feed_gaps`, `log_lag_s`, `alternation_breaks`, `short_recording`). Si un fixture pierde su rareza, `test_live_core_weird_games.py` falla: un fixture sin su rareza no prueba nada.
- Los partidos son los grabados de `tests/recordings/` (`<código>.rec.json.gz` + su `<código>.package.json`); **no se copian**. Cada entrada del catálogo apunta a su código.
- Un partido puede no venir de una grabación en directo: el de la **prórroga** (Getafe–Cultural, `2536139`) es el documento terminado que sirve FEB (igual que Cultural–Oviedo y Oses–Joventut), cortado cada 10 s de partido como hace la reproducción de la app (`RecordingBuilder` + `truncate_doc`); es dato real con cadencia sintética (sin huecos ni retraso del log), y su entrada lo dice en `source`. `periods` indica cuántos periodos tuvo (por defecto 4).
- `pending` lista lo que falta por conseguir (un partido con la tabla corregida #560, un 0-0 por formato de puntos, FBCYL con reloj restante #370, ids que cambian de temporada).

## Qué se comprueba de cada partido (`tests/test_live_core_weird_games.py`)
Se reproduce como lo vive la tablet: UN motor con SU paquete, consultado cada 30 s de la grabación.
1. **Invariantes** de `tests/engine_invariants.py` (las de B1, #544): un parcial solo cuenta el cuarto en juego (#515), un aviso de flujo repetido solo cuenta lo posterior (#517, #619) y quien contradice la última postura lo dice (#568).
2. **Consistencia**: sin fallos, mismas claves de aviso en una segunda pasada (determinismo), cada clave una sola vez y duración de lo jugado, 2400 s (#561).
3. **La rareza sigue ahí** (la sonda del catálogo).

## Cómo añadir uno
1. Graba el partido (`feb-record.yml` / `src/live_core/recording_builder.py`) o toma el de `tests/recordings/` y crea su paquete (`tests/recordings/make_package.py <código>`).
2. Añade su entrada a `index.json`: `id`, `code`, `match` y las `oddities` con su `probe`, el mínimo medido `at_least`, los `issues` y `what` (qué pasó y por qué es raro).
3. **No afirmes lo que los datos no demuestran**: una sonda mide algo del propio partido (si un partido no tiene una rareza estructural, `regression_only` dice por qué está). Si la rareza no tiene sonda, añade la función a `PROBES` en el test y mídela en el partido real antes de fijar el umbral.
4. Con un arreglo, el test de regresión del bug sigue yendo con el constructor `Match` (es el rojo exacto); el partido real es la red de seguridad.
