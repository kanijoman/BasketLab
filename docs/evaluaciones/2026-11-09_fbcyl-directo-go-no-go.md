# Evaluación: ¿publica FBCYL los partidos mientras se juegan? (spike #444)

Parte de la épica #435. Grabación del **7/11/2026, Universidad de Salamanca Meins Avenida – Unileón B.F. León** (1ª División Femenina, grupo A-1, 19:30 en Madrid, final 81–75), hecha por `fbcyl-record.yml` (run 42398409432, artefacto `fbcyl-recording-7298-39731-39609`, 90 días de retención). El grabador sondeó cada ~10,6 s el servicio de streaming de la web de la FBCyL (`streaming.optimalwayconsulting.com/fbcyl/streaming/match-id/{adGameId}`, sin token): 699 lecturas, 681 de ese flujo, 0 errores, 99 cuerpos guardados. Los números de abajo salen de esa grabación; es **un solo partido** y no se sondeó el canal SSE, solo el REST.

**Veredicto: GO.** El flujo crece durante el partido y lleva lo que la app necesita. Condiciones para usarlo, al final.

## Lo que responde el spike

| Pregunta | Respuesta | Dato |
|---|---|---|
| ¿Hay datos en directo? | **Sí** | 97 lecturas distintas del flujo durante el partido; los movimientos pasan de 10 a 593 antes de que termine |
| Cadencia | Una actualización **cada ~1 min** | entre cambios: mediana 64 s, p90 119 s, máximo 353 s; unos 6 movimientos por actualización |
| Latencia | Baja desde el servidor; **la real, sin medir** | un movimiento se ve por primera vez, de mediana, 7 s después de su `timestamp` (p90 10 s, máximo 55 s, 603 movimientos): es lo que tarda nuestro sondeo de 10 s |
| Correcciones | **No se vieron durante el partido** | el número de movimientos no baja y el periodo no retrocede hasta pasadas las 20:24 UTC (ver «Al final del partido») |
| Titulares | En la **primera lectura con datos** | 10 movimientos «Entra al camp» con hora 19:30:08 (la del saque): se ven desde el salto, **no se sabe si antes** (ver límites) |
| ¿Las estadísticas de jugadoras son en vivo? | **Sí** | `teams[].players[].data` cambia durante el partido: tiros, rebotes, asistencias, pérdidas, robos, valoración y `timePlayed`, y las coordenadas de cada tiro (`shootingOf{Two,Three}{Successful,Failed}Point`: `x`, `y`, `eventUuid`) |
| ¿Cuándo dice el calendario «en directo» y «jugado»? | «En directo» en la primera lectura con datos (18:31:03 UTC); «jugado» a las 20:30:59 | el último movimiento real es de ~20:19 y el marcador final se ve desde las 20:25:14: el calendario va **~6 min detrás** del final |

## Lo que hay que saber del flujo

**Los movimientos llegan en bloques.** Cada actualización trae sus movimientos con **una sola** `timestamp` (mediana: 1 hora distinta por actualización), así que esa hora es la del envío, no la de la jugada. Cada bloque cubre un tramo de reloj de juego de mediana 16 s (p90 38 s, máximo 54 s; el reloj `min`/`sec` es tiempo **restante**, #370). La latencia de «cuándo ocurrió la jugada en pista» no se puede medir sin una referencia externa (vídeo o un seguidor), y por la cadencia de ~1 min las reglas de «lo reciente» irán por detrás de lo que ve el banquillo.

**Al final del partido el flujo se vuelve poco fiable.** A partir de las 20:24:53 UTC, tras 593 movimientos, aparecen respuestas que retroceden: periodo 1 con 11–7 y 48 movimientos (20:25:04), 68–63 con 525 (20:29:12) y periodo 1 con 19–18 y 103 (20:30:06), mezcladas con las buenas (609 movimientos, 81–75). No se ha investigado la causa (respuestas antiguas o de otra réplica del servicio). La última lectura del flujo tiene 607 movimientos; el endpoint de después del partido (`msstats`, 609 desde las 20:30:59) tiene **2 más** (ambos del 4.º cuarto, a 9:44 de su inicio): el flujo no los llegó a tener.

**La fuente definitiva sigue siendo `msstats`**, que solo existe cuando el partido termina (tiene `universallyid`).

## Límites de esta evaluación

- Un solo partido, de una sola competición; no se compara con vídeo.
- Solo se sondeó el REST: el **canal SSE** (empuja cada jugada) podría tener menos latencia y no se ha medido.
- El grabador pide el flujo cuando el calendario marca el partido en directo o llega su hora, así que no se sabe si hay datos antes del saque (titulares anticipados).
- La hora de cada movimiento está en hora de Madrid (UTC+1 ese día).

## Qué implica para #446

1. **Fuente de directo**: el flujo REST de streaming (y, si se mide mejor, el SSE), sin token; `adGameId` sale de la fila del calendario ESB.
2. **Descartar lecturas que retroceden** (menos movimientos o un periodo menor que lo ya visto): el cliente nunca debe reiniciar el partido por una respuesta vieja.
3. **El cierre lo da `msstats`**: al terminar, el cliente debe reemplazar lo visto por el documento definitivo, que puede traer movimientos que el flujo no tuvo.
4. **No fiarse del calendario para el final**: va ~6 min detrás de lo que dice el flujo.
5. **Las coordenadas de los tiros vienen en directo**: las zonas de la app se pueden alimentar durante el partido, como en FEB.
6. Medir el SSE y la latencia real con un partido y una referencia externa antes de ajustar las reglas de tiempo reciente.
