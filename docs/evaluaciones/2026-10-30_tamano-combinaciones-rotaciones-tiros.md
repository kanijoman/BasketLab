# Tamaño de Combinaciones, Rotaciones y Tiros publicados (30/10/2026)

Spike [#675](https://github.com/kanijoman/BasketLab/issues/675), parte de [#331](https://github.com/kanijoman/BasketLab/issues/331) (P4 de la épica local-first #326). Medido en solo lectura sobre una copia local de los datos reales (MongoDB 8.2 en la máquina de desarrollo): `PRIMERA_FEB_2025_2026_Liga_Regular_Único` (271 partidos, 17 equipos, todos con `PLAYBYPLAY`, `SHOTCHART` y `DERIVED`). «gz» es el tamaño comprimido, que es el que viaja (el sellado de `web-data` comprime).

## Resumen
1. **Rotaciones es casi gratis**: el resultado de un equipo son ~5 KB y se calcula en 0,1 s (17 equipos ≈ 90 KB por competición). Se puede publicar ya, precalculado por equipo.
2. **Tiros es barato**: 34.276 tiros en la competición (126 por partido), **0,56 MB gz** (con el equipo y el jugador de cada tiro, ~0,7 MB). El navegador cuenta las zonas y las compara con la liga.
3. **Combinaciones es lo caro y lo único que obliga a decidir**: sin mínimos y con el desglose por partido, **0,26–0,31 MB gz por equipo** (tamaños 2 a 5), es decir **~4,5 MB gz por competición de 17 equipos**, y 22–28 s de cálculo por equipo (**~7 min por competición** en Actions). Con los mínimos por defecto de la página (15 min, 5 partidos) baja a 0,19 MB por equipo (~3,2 MB por competición): los mínimos apenas adelgazan la tabla porque lo que pesa es el desglose por partido de los tamaños 3 y 4.
4. **El filtro «Período» no se puede reproducir con lo que hoy devuelve el servidor**: el desglose por partido (`game_log`) trae razones ya calculadas (`ortg`, `efg_pct`…) y no los contadores crudos, así que no se pueden reagrupar los partidos de una ventana de fechas.

## Medidas

### Combinaciones (`LineupService`, por equipo, sin mínimos, con `game_log`)
| Tamaño | Combinaciones (equipo 1 / 2) | Filas de desglose | Crudo | gz | Tiempo |
|---|---|---|---|---|---|
| 2 | 66 / 88 | 1.320 / 1.555 | 0,31–0,37 MB | 0,05–0,06 MB | 6 s |
| 3 | 215 / 253 | 2.708 / 3.319 | 0,70–0,85 MB | 0,10–0,11 MB | 8–11 s |
| 4 | 383 / 418 | 2.382 / 2.919 | 0,79–0,92 MB | 0,09–0,10 MB | 6–8 s |
| 5 | 263 / 292 | 688 / 835 | 0,37–0,43 MB | 0,03–0,04 MB | 2 s |
| **Total** | | | **2,2–2,6 MB** | **0,26–0,31 MB** | **22–28 s** |

Efecto de los mínimos (un equipo, los cuatro tamaños): 0 min/0 partidos → 2,17 MB (0,264 gz); 0/2 → 1,93 (0,248); 5 min/2 → 1,72 (0,228); 15 min/5 (los de la página) → 1,38 (0,190).

### Rotaciones (`RotationService`)
Por equipo: un resumen (jugadores, cinco inicial, concentración de minutos, Gini, CV, sustituciones, stint medio…) de ~5 KB, 0,1 s. No hay nada que reagrupar: la página solo elige el equipo.

### Tiros (`extract_shots`)
34.276 tiros, 2,68 MB crudo / 0,56 MB gz (`x`, `y`, `made`, `zone`); falta añadir el equipo y el jugador para filtrar. La página no filtra por fechas, así que no necesita más.

## Lo que sale de la competición más grande
Para una competición de 17 equipos y 271 partidos: rotaciones ~0,09 MB, tiros ~0,7 MB y combinaciones ~4,5 MB gz, **~5,3 MB en total frente a ~0,5 MB** que pesan hoy `rows/` y `derived/` juntos. Con las 8 competiciones de `config/atlas_refresh.json` (varias con 14–18 equipos y grupos) serían del orden de **25–40 MB** de ficheros sellados, casi todo combinaciones.

## Opciones para Combinaciones
- **A. Tablas precalculadas con los mínimos de la página** (15 min, 5 partidos), por equipo y tamaño, solo temporada completa. ~3,2 MB por competición. La página en modo local solo atendería la configuración por defecto; cualquier cambio de período o de mínimos más bajos seguiría necesitando el API. **No permite apagar Render.**
- **B. Contadores crudos por combinación y partido, sin mínimos** (la tabla `combinación × partido` con los contadores de los que salen todas las cifras: tiros, rebotes, pérdidas, posesiones, puntos a favor y en contra, minutos). Es del orden de 4,5 MB gz por competición, **como hoy, pero el navegador calcula todo** (tamaño, estadística, período, mínimos, último partido) con paridad exacta frente a Python, porque el servidor ya calcula cada combinación partido a partido y las fusiona sumando contadores y recalculando las razones (`_merge_lineup_stats`). Hay que portar `_calculate_final_stats` y la regla de reordenación; los vectores salen del `LineupService` real. **Permite apagar Render.**
- **C. Tramos de cinco jugadores con sus contadores** (el navegador forma los pares, tríos y cuartetos): ~0,6 MB gz por competición, mucho más pequeño, pero las cifras de una combinación se calculan hoy sobre las ventanas de tiempo en que **esos jugadores** coinciden en pista, con contexto entre acciones consecutivas (rebote ofensivo, posesiones): cortar por tramos de cinco puede cambiar algunas cifras. **No garantiza paridad exacta**; haría falta medir cuánto difiere antes de elegirla.

## Recomendación
1. **Rotaciones y Tiros: hacerlos ya** (bloque propio, como Evolución): son pequeños, exactos y de bajo riesgo.
2. **Combinaciones: la opción B**, limitada a la **competición en curso** al principio (≈4,5 MB gz una competición de 17 equipos, ~25–30 MB si fueran todas) y con un **suelo** de minutos totales muy bajo (por ejemplo, descartar combinaciones con menos de 1 minuto en toda la temporada, que no se pueden analizar y son la cola larga) para recortar tamaño sin cambiar lo que ve el usuario con los mínimos habituales. Antes de implementarla conviene confirmar con un barrido cuánto pesa con ese suelo y cuánto cuesta en Actions (≈7 min por competición de 17 equipos, secuencial).
3. **Posesiones (#679)**: el mismo análisis pendiente; sale del play-by-play de cada partido y admite filtros de fecha/local/resultado, así que se parece más a la opción B (salidas por partido y suma en el navegador) que a una tabla fija.

## Reproducir
Scripts de medida (no están en el repositorio: son de un solo uso) leyendo la base local con `MONGODB_CONNECTION_STRING=mongodb://localhost:27017`: `LineupService.get_lineup_analysis(..., min_minutes=0, min_games=0, include_game_log=True)`, `RotationService.get_rotation_analysis(...)` y `extract_shots` del router de tiros.

## Resultado: Combinaciones publicadas (#686, opción B)
Se implementó la opción B (todas las combinaciones, sin mínimos, con los contadores de cada partido; el navegador aplica tamaño, estadística, período, mínimos y último partido). Pesa **la mitad de lo estimado**: el spike midió la respuesta de la API (objetos con nombres de campo, nombres de jugador y `game_log` por combinación) y lo publicado son filas de 22 números por combinación y partido (`COLUMNS` de `lineups_export.py`), con los jugadores y sus nombres una sola vez por equipo. Medido con la base local, todos los tamaños 2–5:

| Equipo | Partidos | Crudo | gz | Cálculo |
|---|---|---|---|---|
| FEB, PRIMERA FEB 2025-26 (2 equipos) | 31–32 | 482–580 KB | **118–141 KB** | ≈ 30 s |
| FBCYL, 1ª fase grupo A (3 equipos) | 5–6 | 43–51 KB | **6–8 KB** | ≈ 5 s |

Una competición de 17 equipos de FEB son **≈ 2–2,4 MB comprimidos** (frente a los ~4,5 MB estimados) y **≈ 8–9 min** al publicar (secuencial: como estimaba el spike, el tiempo lo pone el recorrido del play-by-play de cada partido en cada tamaño, no la forma de la salida). No hizo falta el suelo de minutos totales de la recomendación: se publican **todas** las combinaciones. Queda pendiente, si el tiempo molesta, no recalcular al publicar los equipos sin partidos nuevos (el publicador ya conserva los bytes de lo que no cambia, pero hoy calcula antes de comparar). Paridad exacta con la API: vectores con los partidos reales de las dos ligas y comprobación contra Mongo local (2 equipos de la temporada completa, 4 de otra de FEB y 3 de FBCYL, con los filtros de fechas de Mongo de verdad).
