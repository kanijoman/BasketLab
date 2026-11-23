# Euroliga masculina como fuente externa: spike de la API pública (#1038, D6a de la épica #872)

Medido el 23/11/2026 con la API pública de la Euroliga, sin clave y con un `User-Agent` normal (`Mozilla/5.0`, que no nombra el proyecto). Solo lectura: no se cargó nada.

## Veredicto

**GO para las temporadas 2017/18 en adelante** (`E2017` a `E2025`, más la actual `E2026`). En esas nueve temporadas completas la jugada a jugada **cuadra con la caja oficial en todas las estadísticas, también en las informativas** (72 de 72 partidos medidos). Antes de 2017/18 no es fiable (ver abajo) y se queda fuera.

La Euroliga **femenina** es otro sitio (la organiza FIBA Europe) y sigue pendiente de su spike (#1039).

## Qué da la API

Dos servidores, los dos sin clave:

| Qué | Dónde |
|---|---|
| Competiciones, temporadas (27: `E2000` a `E2026`), partidos de una temporada, detalle de un partido | `api-live.euroleague.net/v2/competitions/E/seasons/{temporada}/games[/{gameCode}]` |
| **Caja** de un partido: jugadores y totales de cada equipo, con la **biografía** de cada jugador | `.../games/{gameCode}/stats` (también en `v3`) |
| **Jugada a jugada** | `live.euroleague.net/api/PlayByPlay?gamecode=…&seasoncode=…` (un bloque por cuarto y prórroga) |
| **Tiros** con coordenadas, zona, jugador y reloj | `live.euroleague.net/api/Points?gamecode=…&seasoncode=…` |
| Caja resumida | `live.euroleague.net/api/Boxscore?gamecode=…&seasoncode=…` |

No existen (404) las rutas `v2` de jugada a jugada y de tiros, ni `v1`: el jugada a jugada y los tiros están solo en `live.euroleague.net`.

**Volumen**: la temporada 2025/26 tiene 402 partidos (380 de liga regular, 16 de play-off, 3 de Final Four y 3 de play-in) y la 2026/27 va con 130 de 380 jugados. **Un partido son 3 peticiones** (caja, jugada a jugada y tiros); una temporada completa, ≈ 1.200 más una del listado: con el presupuesto por defecto de ACB (900) harían falta dos días, así que la fuente llevaría un presupuesto mayor o la primera carga iría por lotes.

## Biografía y ids

* La caja de `v2` trae por jugador `code` (`009849`), nombre, país, **fecha de nacimiento**, país de nacimiento, **altura**, peso y dorsal. En la muestra de 223 jugadores, 223 tienen nacimiento y 222 altura. No hace falta una petición por jugador.
* **El código de jugador es estable entre temporadas**: de los 106 jugadores que aparecen en 2024/25 y 2025/26, los 106 tienen el mismo código, nombre, nacimiento y altura. El jugada a jugada y los tiros lo llevan con un prefijo (`P009849`).
* La posición no viene en estos datos.

## Cuadre de la jugada a jugada con la caja oficial, por temporada

8 partidos por temporada elegidos al azar de los jugados (10 en las dos primeras mediciones de 2024 y 2025). Se comparan por equipo y partido, contra el **total oficial del equipo** (que incluye lo que hizo el propio equipo: rebotes de equipo), las nueve estadísticas básicas (puntos, tiros de 2 y de 3 intentados y anotados, tiros libres, rebotes ofensivos y defensivos) y las informativas (asistencias, robos, pérdidas, tapones y faltas).

| Temporada | Partidos fiables | Nota |
|---|---|---|
| 2017 a 2025 (las nueve) | **8 de 8 en cada una** | cuadran también las informativas |
| 2016 y 2015 | 0 de 8 | fallan los intentos de 2 |
| 2014, 2013, 2012, 2011, 2010, 2009 | 2, 2, 4, 3, 2 y 2 de 8 | fallan los intentos de 2 |
| 2008 | 7 de 8 | |
| 2007 | 0 de 8 | fallan rebotes, intentos de 2 y robos |
| 2006 y 2005 | **sin jugada a jugada** (404) | solo hay caja |

Las temporadas 2002 y 2000 no se midieron: ya en 2005 y 2006 no hay jugada a jugada.

### Lo aprendido para el conversor
* **Los rebotes y las pérdidas solo cuadran con el total oficial del equipo**, no con la suma de los jugadores: el equipo tiene sus propios rebotes (un rebote de equipo no tiene jugador en la caja). Igual que en ESPN.
* **Códigos propios de las temporadas antiguas**: `DUNK` y `LAYUPMD` (tiro de 2 anotado), `LAYUPATT` (tiro de 2 fallado), `3FGAB` (triple fallado) y `CMU` (falta antideportiva). Con ellos mejora 2008 a 2014, pero no se arregla.
* **El límite de las antiguas son los tiros taponados**: un tiro de 2 taponado (`AG`) a veces tiene su fila de intento y a veces no, así que el intento no se puede reconstruir con exactitud. Esos partidos no cuadran y quedarían marcados como no fiables (`_reliable: false`); no se corrigen a ojo.
* Códigos de la jugada a jugada (2017 en adelante): `2FGM`, `2FGA`, `3FGM`, `3FGA`, `FTM`, `FTA`, `O` y `D` (rebote ofensivo y defensivo), `AS` (asistencia), `ST` (robo), `TO` (pérdida), `FV` (tapón), `AG` (tiro taponado), `CM` y `CMT` (falta y falta técnica), `OF` (falta ofensiva), `RV` (falta recibida), `IN` y `OUT` (cambios), `TOUT` y `TOUT_TV` (tiempos muertos), `BP`, `EP` y `EG` (inicio y fin de periodo y de partido), `JB` y `CCH` (salto y reto del entrenador).

## La regla del histórico (decidida el 23/11/2026)

**10 temporadas como horizonte de carga, con tres niveles** (el detalle y la justificación están en OPERATIONS y ROADMAP):

1. **Archivo (privado)**: lo cargable **y fiable** de las últimas 10 temporadas, con el partido completo. No se purga nada de lo ya cargado.
2. **Filas por jugador y temporada** (Talent y Analytics): las mismas 10 temporadas, porque Talent evalúa hasta los 25 o 26 años y seguir a un jugador desde los 16 pide 10 temporadas.
3. **Secciones pesadas** (partidos, tiros, quintetos, jugada a jugada): solo la temporada actual y la anterior (#991).

Para la Euroliga el tope de 10 y la calidad coinciden casi del todo: la temporada 2016/17 queda dentro del tope pero no es fiable, así que **en la práctica entran 9 temporadas más la actual** (2017/18 a 2025/26 y 2026/27).

## Siguiente (si se sigue con la fuente)

Patrón de ACB (#886): catálogo de ediciones pausadas (`league: euroleague`, que hay que añadir a `EXTERNAL_SOURCES`), cliente con pausa y presupuesto, lector, conversor al documento FEB con los códigos de arriba y el mapa de tiros (coordenadas de `Points` a las zonas del motor, con la validación contra la zona que da la propia API), enlace con FEB por nombre y fecha y la fuente del refresco diario. La femenina (#1039) tiene su propio spike.

## Otras competiciones del mismo endpoint (barrido del 23/11/2026)

`/v2/competitions` lista 43 competiciones. Se midió cada una: temporadas, partidos de la última temporada con datos y, en una muestra de partidos jugados, si hay caja (con biografía), jugada a jugada y tiros, y si la jugada a jugada cuadra con la caja (las nueve estadísticas básicas, con los mismos códigos que la Euroliga).

| Competición | Temporadas | Último dato | Fiable desde | Para qué sirve |
|---|---|---|---|---|
| **Euroliga** (`E`) | 2000–2026 | 380 partidos por temporada | 2017/18 (spike) | masculino sénior |
| **EuroCup** (`U`) | 2002–2026 | 2026/27: 224 partidos (128 jugados) | **2017/18** (6 de 6 por temporada de 2017 a 2025; 2016 y 2014 fallan en los intentos de 2; 2011, 3 de 6) | masculino sénior, segundo nivel europeo |
| **U18 Next Generation Tournament** (`J`) | 68 torneos desde 2002; 4 o 5 por temporada desde 2014 (clasificatorios y final) | 2026/27: Rijeka (16 partidos) y Viena | **19 de 19 torneos medidos, de 2019/20 a 2026/27, 3 de 3 cada uno** (≈ 16 partidos por torneo, ≈ 75 por temporada) | **sub-18 de los mejores canteras de clubes europeos: encaja con la formación de Talent**, con biografía en la caja |
| SuperCup (`SC`) | solo 2026 | 4 partidos, 3 de 3 fiables | — | poco: una sola edición |
| Euroleague Qualifying Round (`EQR`) | 2009–2014 | 7 partidos en 2014, **0 de 3 fiables** | no | histórica, sin interés |
| ULEB Summer League (`S`) | 2007 | 0 partidos | no | vacía |
| **Ligas y copas nacionales** (alemana, italiana, griega, española, turca, francesa…, 32 códigos) | 2000–2005 o ninguna | **0 partidos** | no | **no tienen datos**: son códigos heredados sin partidos |

* **Eso significa que la EuroCup y el torneo sub-18 son lo único nuevo** de este endpoint, además de la Euroliga. Misma API, mismos códigos de jugada, misma biografía y mismo identificador de jugador (el código `009849` de la Euroliga sale también en EuroCup y torneos, por lo que el enlace entre competiciones es directo).
* **El torneo sub-18 es la pieza de más valor para Talent**: seguir a los jugadores antes del salto al sénior con caja y jugada a jugada completas, y con el mismo `code` de persona que luego tendrán en la Euroliga.
* **Límite de peticiones**: la API responde **429 (Cloudflare, error 1015) a ≈ 8 peticiones por segundo** (dos barridos en paralelo) y se recupera en unos 2 minutos. Con una sola petición cada 0,3 s (≈ 3 por segundo) se midieron cientos de peticiones sin ningún bloqueo. La fuente debe llevar pausa propia (≥ 0,5 s), un solo trabajo a la vez y espera con reintentos ante un 429.
