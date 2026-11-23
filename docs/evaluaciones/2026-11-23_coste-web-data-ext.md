# Por qué `web-data-ext` tarda más de una hora con NCAA y qué se hizo

Medido el 23/11/2026 con **partidos reales de NCAA** (los de la conferencia ACC masculina del archivo externo, solo los fiables) pasados por la misma publicación que usa el workflow (`publish_web_data`, secciones incluidas), con `cProfile`. No hay `mongod` ni Docker en la máquina de trabajo, así que se midió con `mongomock`: **los tiempos absolutos no valen** (Mongo real es varias veces más rápido en las agregaciones), pero **el reparto entre secciones y cómo crece con el número de partidos sí**, porque lo que domina es Python.

## Qué se vio

| Partidos | Tiempo total | `inout` | `lineups` | filas (`export_collection`) |
|---|---|---|---|---|
| 10 | 49 s | 18 s | 18 s | 4 s |
| 30 | 224 s | 134 s (60 %) | 53 s (24 %) | 13 s (6 %) |

* **Las secciones `inout` y `lineups` son el 84 % del tiempo.** Las filas y los tiros pesan poco.
* **`inout` crece al cuadrado**: de 10 a 30 partidos (3×) pasa de 18 s a 134 s (7,4×). Para cada jugador de la colección (`export_inout` llama a `inout_analysis` por jugador) el repositorio recorre **todos los partidos de la colección** y, de los de su equipo, vuelve a analizar la jugada a jugada completa; los compañeros de equipo repiten el mismo análisis. Con ≈ 370 partidos por conferencia (la ACC) es la diferencia entre minutos y horas, y con una temporada completa por conferencia, más.
* **`lineups` crece linealmente, pero era 264 veces más caro de lo necesario**: `LineupStatsCalculator._get_lineup_segments` recorre **todos los instantes del partido (cada 5 s) para cada quinteto** y pregunta al extractor quién está en pista, algo que depende del equipo y del instante y nunca del quinteto. Para 30 partidos reales eran 3,9 millones de llamadas.

## Qué se hizo (esta entrega)

* **`LineupExtractor` recuerda quién está en pista por (equipo, instante)** y la plantilla del equipo (un partido no cambia mientras vive el extractor); devuelve una copia del conjunto, porque quien llama puede modificarlo. Con 10 partidos reales los quintetos pasan de **18,4 s a 6,3 s (3×)**; en un partido de 264 quintetos los recorridos de tramos de pista pasan de **1.267.200 a ≤ 4.810**. Las respuestas no cambian: los 236 tests de quintetos, rotaciones y repositorio, y los ficheros dorados de `inout` y de conteo de la jugada a jugada, siguen en verde. También acelera `web-data` de FEB, que usa el mismo código.

## Lo que se hizo después: `inout` en un solo recorrido (opción 1, decidida el 23/11/2026)

`get_players_in_out_stats` (repositorio) calcula el dentro/fuera de **todos los jugadores de la competición en un solo recorrido de los partidos**: cada partido se lee una vez y su analizador lo comparten los jugadores que lo necesitan. El resultado de cada jugador es **idéntico** al de la consulta por jugador (`get_player_in_out_stats`, que sigue existiendo como oráculo; los escenarios del corpus real del repositorio y los 36 jugadores de los partidos de prueba de FEB lo comprueban). `export_inout` lo usa.

| Partidos | `inout` antes | `inout` ahora |
|---|---|---|
| 10 | 18 s | **7 s** |
| 30 | 134 s | **16 s** |

Ahora crece **linealmente** (de 10 a 30 partidos, 2,3× en vez de 7,4×): con los ≈ 370 partidos de una conferencia la diferencia es de horas a minutos. Junto con la memoria del extractor de quintetos, la publicación de 30 partidos pasa de 224 s a unos 40 s (mismo método de medida, `mongomock`).

**Lo que sigue pendiente**: dentro de cada partido, cada jugador sigue recorriendo la jugada a jugada completa (clasificar cada jugada una vez y repartirla entre los jugadores sería un paso más, que se hará si la medición con Mongo real lo pide) y el tiempo real del próximo `Web data ext` en el workflow, que es lo que decide si hace falta además un límite de tiempo propio o saltarse secciones.
