# +/- del motor live frente al PDF oficial de FEB (27/10/2026, #594)

Pregunta: el +/- de cada jugador del motor (`players[*].pm`) difiere del PDF en unos pocos partidos. ¿Es un fallo del motor, del orden en que se aplican las líneas, o un límite de los datos?

## Método
- `pdftotext -raw` del PDF de cada partido (`BoxScore.aspx?p=<código>&c=4&qd=4&t=FINAL`, ver [pdf-ground-truth](2026-10-16_pdf-ground-truth.md)); columna `+/-` por jugador, emparejada con los jugadores del boxscore del partido por orden y comprobada con los puntos de cada jugador (los partidos que no se pueden emparejar se descartan).
- Motor: `LiveEngine().update(documento)` y `pm` de cada jugador.
- Muestras: 4 partidos grabados de 2026/27 (fixture `tests/fixtures/feb_pdf_player_ground_truth.json`), 37 partidos de LF2, LF Endesa y LF Challenge 2025 (`data/historical_games`) y 36 de 2026/27 exportados de Mongo.

## Resultados
| Muestra | Partidos | Jugadores exactos | Jugadores con diferencia |
|---|---|---|---|
| Histórico 2024-25 (LF2, LF Endesa, LF Challenge) | 37 | **790 de 790** | 0 |
| 2026/27 exportados de Mongo | 36 | 803 de 821 | 18, en **2 partidos** (2535747: 14 jugadores por ±1; 2535757: 4 por ±2) |
| 2026/27 grabados | 4 | 77 de 90 | 13: 2536311 (11 por ±2 y ±4), 2524470 (2 por ±1) |

- **En el 95 % de los partidos el +/- del motor es exacto** (73 de 77) y **la suma por equipo coincide siempre con el margen del partido**: lo que cambia es **a qué compañeros** se les acredita un punto, nunca cuántos puntos hubo.
- Las diferencias son de 1 a 4 puntos y vienen todas de **cuándo se aplica una tanda de sustituciones respecto a tiros libres o canastas del mismo segundo o del siguiente** (por ejemplo, las sustituciones del descanso, anotadas 15 minutos después con el reloj en 10:00 del tercer cuarto, y el primer tiro libre del cuarto: el PDF lo reparte a los que estaban antes).

## Lo que se probó para arreglarlo (y por qué no hay arreglo)
- Ordenar primero las sustituciones, o primero los tiros libres, dentro del mismo reloj: deja de coincidir en los partidos exactos (de 77 a 29-49 jugadores exactos de 90).
- Ordenar por la hora real de anotación (`LogTimeUtc`): arregla 2535747 (14 → 0) pero rompe 5 partidos que hoy son exactos (de 0 a 2-4 jugadores) y las ventanas de 2536311 solo mejoran a la mitad.
- Buscar, por ventana de «balón parado» (faltas, tiros libres, sustituciones, tiempos muertos), la ordenación que mejor encaja con el PDF: en 2536311 queda un residuo (22 de 56) sin ningún patrón observable en el feed; con libertad para mover cada sustitución se llega a 0 pero es un sobreajuste (13 sustituciones movidas sin regla común).
- Conclusión: el PDF reparte esos puntos con un orden de eventos interno de FEB (el de entrada del anotador) que **no está en el feed**; ninguna regla sobre `num`, reloj ni `LogTimeUtc` lo reproduce sin romper los partidos que hoy son exactos.

## Decisión
No se cambia el motor. El +/- de la pestaña Boxscore sale del orden de las líneas del feed (`num`), que es exacto en el 95 % de los partidos y con la suma de equipo siempre correcta; en el resto, a algún jugador le puede salir 1-4 puntos distinto del PDF. Test de guarda: `tests/test_live_core_boxscore_pdf.py` (≥ 75 % de jugadores exactos y nunca más de 4 de diferencia en los 4 partidos grabados). Se reabre si FEB cambia el feed (por ejemplo, si publica la hora real de cada sustitución).
