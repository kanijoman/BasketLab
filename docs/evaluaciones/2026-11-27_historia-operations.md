# Historia de OPERATIONS.md (incidentes, mediciones y cronología)

Pasajes movidos tal cual de [OPERATIONS.md](../OPERATIONS.md) el 27/11/2026: casos reales, mediciones fechadas y cronología por issue. La regla o el contrato que dejó cada uno vive en OPERATIONS.md.

## Grabador FBCYL: fiabilidad (#446, 23/11/2026)

- el sábado 21/11 el partido de las 17:00 no se grabó. **Causa real (hallada el 23/11): el grabador pedía todo con `requests.get(url)` sin cabeceras y los servidores de FBCYL (el calendario del ESB, las estadísticas y el streaming) cierran la conexión sin responder al agente por defecto de `requests`**: con un `User-Agent` normal responden 200 (medido en los cuatro endpoints). El planificador devolvía «sin partidos» sin dejar rastro y el grabador tampoco habría podido leer nada; `http_get` envía ahora un `Mozilla/5.0` llano. Además, el cron de GitHub tampoco disparó entre las 14:22 y las 20:38 UTC. No hay que depender de lanzarlo a mano.

## Atlas retirado (#724)

- El workflow de comparación (*Atlas compare*) cumplió su función —la última ejecución, en verde, dio el archivo con todo lo que tenía Atlas: 77 colecciones y 2.309 partidos— y se retiró con sus módulos y tests;

## Catálogo de competiciones: alta en un solo sitio y alcance en Atlas (#724, #456)

- ; antes eran cuatro ficheros que se desincronizaban
- y de 3ª FEB solo el grupo A-B en Atlas (el plan gratuito de 512 MB no admite sus 10 subgrupos: ≈ 3.370 partidos/temporada ≈ 0,13 MB cada uno en disco, medido en LF Challenge; 3ª FEB son 1.768).
- **Sin ese límite** (archivo y base local):

## Refresco de fuentes externas: carrera del push (#1068)

- como el de FIBA que terminó en 2 minutos mientras NCAA llevaba 34,

## Fuente FIBA: activación escalonada (#887)

- el 18/11/2026 se activó primero `fiba-u18-eurobasket-2025`, 56 partidos, como comprobación de la cadena real —workflow, Mongo efímero, clave del archivo externo, `git push` y `web-data-ext`—; después, con el cuadre arreglado, los otros 21: juveniles 2024-2026 y los absolutos de 2025,

## Fuente NCAA: primer lote real (#888, 23/11/2026)

- **Medido en el primer lote (23/11/2026, 2.000 peticiones, 34 minutos: ≈ 1 petición por segundo)**: 1.821 partidos nuevos (10 conferencias masculinas, por el orden del catálogo), **≈ 9,8 KB comprimidos por partido** (17,9 MB), **98 no fiables (5,4 %)** —en la ACC, 16 de 371: 2 sin jugada a jugada y el resto con diferencias sueltas, sobre todo triples intentados—, `partial: true` y `last_ok` sin mover, como estaba previsto; el primero salió en rojo por la carrera del push (#1068, corregida). **Una temporada son ≈ 108 MB comprimidos: con 10 temporadas serían ≈ 1,1 GB, así que #967 (los ficheros pesados como assets de release) pasa a ser necesario antes de cargar más de una o dos temporadas de NCAA.**

## NCAA: respuesta cortada (#1088, 24/11/2026)

- el segundo intento del lote murió tras ~20 minutos con `IncompleteRead(645685 bytes read)`:

## NCAA: un partido ilegible tumbaba la ejecución (#1086, 24/11/2026)

- el lote del 24/11 falló con `NcaaPageError: the game is not in the expected format (KeyError: 'id')` porque la fuente fallaba al final del recorrido de **cada entrada** si todos los partidos nuevos de esa entrada eran ilegibles (una conferencia con uno solo, malformado, tumbaba todas las siguientes y la fecha de arranque no avanzaba). Ahora `NcaaSource.finish()`

## NCAA: coste de la publicación y qué se hizo (#888, 23/11/2026)

- el `Web data ext` del primer lote (1.821 partidos) llevaba más de 90 minutos. Perfilado con partidos reales de NCAA (la ACC, con `mongomock`: valen el reparto y el crecimiento, no los tiempos absolutos), **`inout` y `lineups` eran el 84 % del tiempo** y las filas el 6 %. (1) **`inout` era cuadrático**: por cada jugador se recorrían todos los partidos de la colección y se reanalizaba la jugada a jugada de los de su equipo (10 partidos: 18 s; 30: 134 s); ahora

## Histórico: decisión de publicación del 19/11/2026 (#991)

- Motivo: con las tandas 1 y 2 cargadas `web-data` pesaba 209 MB (la estimación de las cuatro tandas era 84 + 60–190 MB).
- , que sustituye a la del 13/11** (el detalle completo de todas las temporadas antiguas en `web-data`)

## Tandas del histórico: tanda 1 (#876)

- ; el refresco que la cargó, el 16/11, tardó ≈ 80 min y quedó en rojo por 404 de partidos sin caja; los siguientes, 6-7 min

## Colecciones cerradas: medición tras #924 (13/11/2026)

- **Medido el 13/11/2026 con #924 en `main`**: el primer refresco (comprueba todo, deja el estado guardado) 17 min, con el scrape en 13 min (antes 25 y 23); el segundo, **5 min 14 s en total y 1,5 min de scrape: 304 de 366 colecciones cerradas y 62 comprobadas**, 0 partidos nuevos. Lo que queda es **restaurar y guardar el archivo (43 s + 2,3 min, el 57 % del run)**, que crece con su tamaño (111,9 MB hoy): las temporadas anteriores a la actual y la previa se archivan «ligeras», sin jugada a jugada.

## DERIVED: el refresco local no lo rellenaba (#630)

- : el local no lo hacía y dejó 167 partidos fuera de «Análisis pbp»

## Archive refresh: partido en juego 2537218, Atlas, incomparecencias (#724, #902, #950)

- Sin esto, el partido 2537218 de 3ª FEB B-B (jugado el 11-10-2026, aún «SCHEDULED» con los cuatro cuartos en FEB) se saltaba en cada refresco y dejaba el run en rojo siempre, ocultando los fallos de verdad (con el refresco de Atlas no se veía porque solo cubría el grupo A-B).
- *Archive refresh* corre en paralelo al *Atlas refresh* hasta que éste se retire; `web-data` espera ahora a *Archive refresh* y `live-packages` sigue esperando al de Atlas hasta el paso 4 de #724.
- ; son los dos del CE SSAA Cadete Fem. 2025/26 que mantuvieron en rojo el primer refresco programado tras #902
- ; hasta entonces ninguno tenía fecha y solo se perdonaban las incomparecencias: con la tanda del histórico, cuatro partidos de 2022-23 y 2023-24 sin boxscore en FEB dejaban rojo cada refresco

## Archive refresh: límite de tiempo (#1067, 23/11/2026)

- , así que un scrape que gastaba todo el tiempo perdía todo lo descargado, y una carga siempre mayor que el límite habría fallado para siempre. Ahora

## Coste del refresco: medición del 13/11/2026 (#924)

- **Medido el 13/11/2026** (run a mano de 25 min, línea de tiempo del runner con las marcas de Mongo): restaurar el archivo 23 s · **fase FEB 20 min para 327 colecciones sin ningún partido nuevo (≈ 3,7 s por colección)** · fase FBCYL 2,9 min para 37 grupos y 368 partidos nuevos (≈ 0,5 s por partido) · guardar el archivo 80 s. Hasta el 11/11 (≈ 85 colecciones activas) un refresco normal tardaba 3–7 min; desde el 12/11 (≈ 330, con el histórico de 2024 y 2025) 25–29:

## Partidos que fallan: umbrales anteriores (#1021)

- (20 y 7 hasta #1021: las tandas del histórico dejaban el run en rojo una semana)

## web-data: alta y baja (#1082) y tiempo de construcción (#944)

- **Medido el 25/11/2026** (tiempo de «Build the artifacts» en runs limpios de Web data): 1.430–1.686 s antes de la baja y 1.944–1.974 s leyéndolas en cada publicación (+4 a +9 minutos, +20 a +35 %), de ahí el cambio; el
- , el 16/11/2026 un cambio de `src/live_core` recalculó `lineups` e `inout` en las 366 competiciones y a los 120 min de entonces solo llegó a 352 —63 min de combinaciones y 36 de IN/OUT—, así que no publicó y cada refresco siguiente habría vuelto a empezar

## Live packages: guarda de fases, el caso real (#724)

- Pasó de verdad: el primer refresco que sembró los metadatos en el archivo fue uno parcial (`only: tercera feb`) y los paquetes salieron con 3 rivales y las rondas de una sola competición en vez de 12 y las de ocho.

## Protocolo de despliegue: casos reales (#789, 06/11/2026)

- : el 06/11/2026 el *Web data* falló en LF Endesa por una jugada sin equipo que la base local no tenía, y paró la publicación de todo
- antes un run rojo empujaba los ficheros que había calculado hasta fallar y los dejaba huérfanos en la rama;

## Dependencias: estado del 23/10/2026 (#526)

- Estado del 23/10/2026: la app live sin avisos; el frontend sin avisos (0 vulnerabilidades) tras subir `jspdf` (crítico), `axios`, `dompurify`, `lodash`, `form-data` y `react-router-dom` a la 7 (#526).

## Memoria: workers por defecto (#163)

- Antes `run_api.py` lanzaba 4 en Linux → ~500-700 MB en reposo y OOM intermitente al desplegar.

## Google Play: el keystore se creyó perdido (11/11/2026)

- (el 11/11/2026 se creyó perdido: estaba solo en un Drive)
