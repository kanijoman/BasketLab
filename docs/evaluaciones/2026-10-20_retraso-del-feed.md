# Retraso del feed de FEB y frecuencia de sondeo — Zamora–León y León–Unibasket (LF Challenge)

**Qué es**: en la prueba del fin de semana el staff vio que el feed iba a veces más de un minuto por detrás del partido, y se preguntó si convenía bajar el intervalo de sondeo (10 s). Se ha medido con las dos grabaciones reales (códigos 2524470 y 2524475; la segunda con los sondeos y las cabeceras de FEB sin procesar, `recording_report`).

**Cómo leerlo (límites)**
- Mide lo que **FEB publica**: cada línea del play-by-play trae `LogTimeUtc`, la hora en que la mesa la anotó. El retraso de una línea es el tiempo entre eso y el sondeo que la vio por primera vez. **No** incluye lo que tarda la mesa en anotar una jugada (no se ve en los datos): el desfase que ve el entrenador respecto a la pista es este más el de la mesa.
- Dos partidos, con el grabador de CI sondeando cada 10 s (mediana real entre sondeos: 11-12 s). Los números de la app serán los suyos: la app ahora los mide (ver abajo).

## 1. Cuánto tarda en llegar una línea

| | Zamora–León | León–Unibasket |
|---|---:|---:|
| Líneas medidas | 458 | 419 |
| Mínimo | 13 s | 12 s |
| Mediana | **42 s** | **42 s** |
| Percentil 90 | 60 s | 59 s |
| Máximo | 106 s | 94 s |

(`recording_report` sobre las peticiones sin procesar de León–Unibasket da mediana 39 s y p95 61 s sobre 140 cambios.) **El «más de un minuto» es la cola alta: el 10 % de las líneas tarda 1 minuto o más, y alguna llega a minuto y medio.**

## 2. De qué se compone

- **Caché de FEB.** Todas las respuestas llevan `cache-control: public,max-age=15` y la cabecera `age` dice cuánto llevaba la respuesta en caché: **mediana 11 s, p90 22 s, máximo 27 s (KeyFacts) y 37 s (BoxScore)**. Es retraso que no se puede quitar sondeando más: el servidor devuelve el mismo objeto hasta que caduca.
- **Nuestro sondeo.** Con un intervalo de P segundos, una línea espera de media P/2: **5 s** con 10 s.
- **El resto (~25 s de la mediana)** es FEB: lo que tarda en publicar la línea tras anotarla.

Solo el sondeo (≈ 5 de ~42 s) depende de nosotros.

## 3. ¿Conviene bajar el intervalo?

| Intervalo | Espera media por sondeo | Peticiones por hora (3 endpoints) |
|---|---:|---:|
| 5 s | 2,5 s | 2160 |
| **10 s (actual)** | 5 s | 1080 |
| 15 s | 7,5 s | 720 |

Solo **el 28 % de los sondeos trae novedades** (152 de 543 en KeyFacts): con 5 s, la mayoría devolvería la copia en caché. Bajar a 5 s ganaría ~2,5 s de ~42 (un 6 %) duplicando las peticiones a un servicio que no es nuestro; subir a 15 s costaría otros 2,5 s y ahorraría un tercio. **Conclusión: se deja en 10 s.** Si el retraso molesta, el margen real está en FEB y en la mesa, no en la app.

Evitar la caché añadiendo un parámetro a la petición podría quitar los ~11 s de mediana, pero **no se ha probado ni se recomienda sin hablar con FEB**: la caché pública es una decisión suya y saltársela multiplica la carga sobre su origen.

## 4. Qué mide ahora la app

`feed/feedLag.ts` (`FeedLagMeter`), con los datos de cada documento (`LiveFeed.onDocument`): el retraso de cada línea nueva, la edad de la caché (`age`, solo en la app nativa: el navegador no deja leer cabeceras de otro origen) y la proporción de sondeos con novedades.
- Mientras hay conexión, el panel dice «Datos de FEB con unos 42 s de retraso (el 90 % llega en menos de 60 s)» (con ≥ 5 líneas; si el reloj de la tablet va por detrás de FEB lo avisa en lugar de dar un número absurdo).
- Al terminar o desconectar, el registro de sesión recibe una nota: «Retraso de los datos de FEB: mediana … s, p90 … s, máx. … s (n líneas); caché de FEB: … s de mediana; … % de los sondeos traen novedades». Con ella, cada partido que se siga en directo aporta su propia medida.

**Pendiente de datos reales**: repetirlo con los partidos que siga la app (la nota queda en el diagnóstico) y con la red del pabellón, por si el retraso allí es distinto.
