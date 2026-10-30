# Posesiones publicadas (30/10/2026)

Estudio y resultado de [#679](https://github.com/kanijoman/BasketLab/issues/679), parte de #331 (P4 de la épica local-first #326). Medido en solo lectura con una copia local de los datos reales (`PRIMERA_FEB_2025_2026`, 271 partidos, 17 equipos; y la colección FBCYL real).

## Resumen
1. **El endpoint no tiene filtros**: `GET /possessions/{collection}` solo recibe la colección (el cliente enviaba local/visitante, resultado y fechas y el router los ignoraba). Posesiones es una **tabla de temporada por competición**: no hace falta guardar salidas por partido ni sumar en el navegador, como se temió en el primer planteamiento.
2. **Se publica precalculado con el mismo código** que ejecutan los endpoints, así que es **exacto por construcción** y no hay nada que portar ni vectores de paridad: tabla, consistencia (`get_consistency`) y los dos CSV de la página.
3. **Pesos reales** (comprimidos): tabla + consistencia + CSV de calidad, 0,02 MB (FEB) y 0,01 MB (FBCYL); CSV por posesión, 0,36 MB (39.388 filas de 271 partidos) y 0,03 MB. El CSV grande va en su sección y solo se descarga al pulsar el botón.
4. **Coste en el publicador**: ~9 s por competición (la tabla recorre el play-by-play de cada equipo), 3 s el CSV.

## Qué se publica
| Sección | Contenido | Se lee |
|---|---|---|
| `possessions/` | tabla (34 campos por equipo), consistencia de los equipos (propia y del rival) y CSV de calidad | al abrir la página |
| `possession_csv/` | el CSV por posesión | al pulsar «Exportar CSV» |

Las dos descargas dejan de ser enlaces al API: la página hace el fichero en el navegador con el texto publicado y **un solo BOM UTF-8** (Excel lo necesita) al principio.

## Fallos del API que salieron al hacerlo (corregidos, con test de regresión)
- **BOM repetido**: los endpoints codificaban cada trozo (las filas de un partido) con `utf-8-sig`, así que el BOM se escribía al principio de **cada partido**: la primera celda de la primera fila de cada partido empezaba con un U+FEFF invisible. El fichero lleva ahora un BOM al principio. El texto de los CSV se hace en un solo sitio (`csv_chunks`) y lo usan el endpoint y la publicación.
- **FBCYL daba un 500**: `TeamStatsService.get_possession_stats` pasa el id de equipo de FBCYL (`teamIdExtern`, un entero) tal cual y el filtro del repositorio llamaba a `.isdigit()` sobre un `int`; la tabla de Posesiones no funcionaba en ninguna competición FBCYL. Lo detectó el exportador con la colección real.

## Reproducir
Con `MONGODB_CONNECTION_STRING=mongodb://localhost:27017`: `export_possessions(handler, colección)` y `export_possession_csv(handler, colección)` de `src/local_data/possessions_export.py`.
