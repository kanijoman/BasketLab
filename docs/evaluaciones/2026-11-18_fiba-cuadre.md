# Evaluación de la fuente FIBA: la ficha pública y su cuadre (18/11/2026)

Parte de #887 (D3a, épica #872) y informe de cuadre de la fuente que pide el criterio común de #884 (jugada a jugada frente a caja oficial). Sigue al spike #915 ([informe](2026-11-13_formacion-fbcyl-fiba.md)), que dejó pendiente la caja por partido.

## Resumen
1. **La ficha pública de FIBA trae la caja oficial por jugador y partido, sin clave ni API.** El spike creía que solo la daba la API (con la clave que la página da a cada navegador) y que esa API no traía asistencias, robos, pérdidas, tapones ni faltas. Está todo en el HTML: los datos de la página (`self.__next_f`, el formato de Next) llevan el partido, **la caja oficial de cada jugador** (puntos, tiros, rebotes ofensivos y defensivos, asistencias, robos, pérdidas, tapones, faltas, faltas recibidas, **minutos y quinteto inicial**), **los totales oficiales de cada equipo**, las plantillas y **la jugada a jugada completa por periodo**. Se descarta depender de la clave (decisión 1 del spike): no hace falta ni para los minutos.
2. **La jugada a jugada reproduce la caja oficial en todas las estadísticas.** Sobre seis partidos reales (12 equipo-partido): las nueve estadísticas centrales y las cinco informativas cuadran **12 de 12** en todas. Antes, con una comprobación previa a este informe sobre 7 partidos del U18 EuroBasket 2025 (160 jugador-partido, 14 estadísticas por jugador): **0 diferencias**. FEB, en cambio, tiene desajustes conocidos (asistencias ±1–2 en ≈ 45 % de los equipos-partido, #378).
3. **Los minutos salen de las sustituciones y el quinteto inicial de la ficha**: 133 jugador-partido, **todos a 1 s o menos de los oficiales** (105 exactos; el resto, redondeo). Resuelve el pendiente del spike y da la base de #963.
4. **Tres particularidades de la fuente**, descubiertas con datos reales y ya cubiertas por tests (abajo).

## Datos
Seis fichas reales capturadas con `scripts/capture_fiba_fixtures.py` (`tests/fixtures/fiba/`), tres competiciones y los dos sexos:

| Partido | Competición | Marcador | Periodos | Eventos | Jugadores |
| --- | --- | --- | --- | --- | --- |
| 125809 France - Austria | FIBA U18 EuroBasket | 95-56 | 4 | 598 | 23 |
| 125803 Italy - Germany | FIBA U18 EuroBasket | 85-71 | 4 | 545 | 23 |
| 125812 Sweden - France | FIBA U18 EuroBasket | 43-94 | 4 | 601 | 24 |
| 125859 Latvia - Slovenia | FIBA U16 Women's EuroBasket | 69-70 | 4 | 598 | 21 |
| 123004 Great Britain - Lithuania | FIBA EuroBasket | 70-94 | 4 | 565 | 22 |
| 123043 Sweden - Spain | FIBA Women's EuroBasket | 75-78 | **5 (`OT1`)** | 599 | 20 |

Se reproduce con `python scripts/fiba_reconciliation_report.py` (el informe de abajo es su salida) y lo guarda `tests/test_fiba_reconciliation_report.py`.

## Resultado del cuadre
| Estadística | Equipo-partido que cuadran | Tipo |
| --- | --- | --- |
| PTS, FGM, FGA, 3PM, 3PA, FTM, FTA, ORB, DRB | 12 de 12 cada una | central |
| AST, STL, BLK, TOV, PF | 12 de 12 cada una | informativa |
| Minutos (desde las sustituciones) | 133 jugador-partido, 105 exactos, el peor a 1 s | aparte (#963) |

Umbrales acordados (#884): las nueve centrales exactas o el partido es no fiable; las informativas se informan sin descartar. Aquí ninguna falla.

## Medido con scripts desechables (no están en el repositorio)
- **Cobertura de la web actual**: se recorrieron los 56 partidos del U18 EuroBasket 2025 y los 76 del EuroBasket 2025 masculino (una petición cada 2 s): **ninguna ficha genérica** en ~132 peticiones (el spike vio 2 de 10; el cliente de D3b reintenta igualmente) y **ninguna prórroga** en esos 132. La prórroga del fixture se buscó en otros eventos: el Suecia–España del EuroBasket femenino 2025. FIBA la llama `OT1`.
- **Estructura**: el EuroBasket absoluto masculino (76 partidos) y femenino (36) de 2025 tienen la misma estructura que los de formación; la Copa del Mundo 2023 no muestra partidos con ese formato.

## Particularidades de la fuente (descubiertas con datos reales)
1. **Los totales de equipo de FIBA ya suman lo que hizo el propio equipo.** En el 125809, 63 rebotes de jugador + 8 de equipo = 71 = 11+33+8+19 (los totales oficiales). El contador de FEB no cuenta los rebotes de equipo, así que el `TOTAL` del documento es la suma de jugadores y lo del equipo va en `TEAMACTIONS`: juntos son la cifra oficial de FIBA, sin perder nada.
2. **Una sustitución puede ser un evento o dos.** En los partidos de formación son dos eventos (entra, sale); en el EuroBasket absoluto es **uno solo** con quien entra (`pId`) y quien sale (`p2Id`). Si se leyera solo la entrada se perderían las salidas y con ellas los quintetos y los minutos. El conversor siempre escribe dos líneas, la del que sale primero.
3. **«Ha jugado» no es fiable; los minutos sí.** En el 125803, Clemens Sokolov está en pista 1:14 (lo dicen las sustituciones y la caja oficial) y la ficha lo marca `HasPlayed: false` sin ninguna estadística. Un jugador «participó» si tiene el indicador **o** minutos.

## Decisiones y límites
- **Sin clave**: la caja completa sale del HTML público. La web de FIBA es de Next y su formato puede cambiar: `parse_game` lo detecta (`FibaPageError`, o `GenericPage` para la versión genérica) en vez de dar una cifra rara.
- **Alcance de D3** (decidido el 18/11/2026): los eventos medidos (U16, U18, U20 EuroBasket, U19 Copa del Mundo, 2024–2026) más las selecciones absolutas de la web actual; **fuera**: el archivo antiguo («desde ~2006», otro formato, sin explorar), las divisiones B y C, los «líderes» (una tabla de 50 jugadores que se calcula mejor desde los partidos).
- **Sin mapa de tiro por ahora**: FIBA da las coordenadas de cada tiro (`x`, `y`); llevarlas a las zonas del motor es un bloque aparte y necesita calibrarse.
4. **Los rebotes se leen de la etiqueta, no del último tiro fallado.** En la primera carga real, 7 de 56 partidos no cuadraban solo en rebotes ofensivos/defensivos: FIBA no escribe los eventos en el orden de su reloj y inferir el tipo del último fallo se equivoca. El cuadre usa la etiqueta del texto (`offensive`/`defensive`, con o sin mayúscula) y solo infiere cuando el texto no dice ninguna.

- **Seis partidos son una muestra pequeña** (tres competiciones, un solo año, una prórroga): el cuadre se repite sobre cada edición y categoría nueva en D3b, y un partido que no cuadre se guarda marcado como no fiable, nunca se corrige.

## Siguiente
D3b (la fuente: descubrimiento de partidos de cada evento, descarga con reintentos y cortesía, catálogo, plantillas con la biografía), D3c (enlace de identidad FIBA↔FEB, con #885) y #963 (minutos en `reconcile_game`, con esta medición como punto de partida).
