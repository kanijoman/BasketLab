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

## Lo que queda (decisión pendiente)

`inout` no mejora con eso (18 s antes y después): cada jugador crea sus propios extractores. Opciones:

1. **Un solo recorrido por partido**: analizar cada partido una vez y repartir el resultado entre todos sus jugadores (lineal en vez de cuadrático). Es lo correcto, pero toca el repositorio de dentro/fuera; el oráculo es el cálculo por jugador actual (los dorados y una comparación jugador a jugador con los partidos de prueba de FEB y FBCYL).
2. **No publicar `inout` ni `lineups` de las fuentes externas** (un indicador por competición en el catálogo). Rápido, pero se pierde el dato.
3. **Un límite de tiempo propio de `web-data-ext`** que publique lo construido y aplace el resto (como el de #1067), sin arreglar el coste.
