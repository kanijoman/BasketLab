# FBCYL en directo: cómo abre la web de la FBCyl el canal SSE (#805, paso 1)

Parte de la épica #435 y sigue a [la evaluación del directo de FBCYL](2026-11-09_fbcyl-directo-go-no-go.md) (#444/#446). **Solo lectura**: se leyó el HTML público de `https://www.fbcyl.es/directos` y su bundle público `react/dist/main.js` (v0.3.17, 7,3 MB, minificado). Más abajo, el resultado de **un único sondeo** al canal que el usuario autorizó (403).

## Lo que hace la web
1. Carga la lectura inicial del partido por REST (`GET {streaming}/streaming/match-id/{adGameId}`, la misma que sondea nuestro grabador) y de ella toma `visibility.pushClientId` **si el servidor lo da**; si no, el navegador genera uno (`client-<crypto.randomUUID()>`).
2. Abre el canal con `EventSourcePolyfill` (el `EventSource` nativo no deja poner cabeceras) en `{streaming}/streaming/register/{conexión}/{clientId}` y **con una sola cabecera: `federation: fbcyl`**. El `{streaming}` es el mismo servicio de nuestro REST.
3. Al terminar el partido (calendario con `universallyid`) cierra el canal con `GET {streaming}/unregister/{conexión}/{sesión}` y redirige a las estadísticas.

## Qué dice de la credencial
- La cabecera `federation` es un **parámetro de enrutado del servicio**, que atiende a varias federaciones con el mismo servidor (la base `{streaming}` ya lleva `/fbcyl/` en el camino, también la del registro; la cabecera lo repite): no es un secreto ni una identidad de navegador.
- El HTML de la página incrusta además un **JWT** (`data-jwt`, 15 minutos de vida, emitido por el servidor de la web). Los interceptores `Authorization: Bearer` del bundle son los de las llamadas del cliente REST de la web; **el canal SSE no los lleva**: sus cabeceras son solo las de `federation`. (El nombre minificado `Ra` podría sombrearse en otro módulo; con un bundle plano, como este, es improbable, pero no se ha ejecutado el código para comprobarlo.) Ese token **no se debe usar desde fuera**: está emitido a la sesión de la web de la federación.
- El `pushClientId` es el único valor que el servidor reparte para registrar un cliente. **No está en nuestras lecturas guardadas** (`fbcyl_streaming_20261107` solo conserva `readings` y `msstats`): no sabemos si el REST lo trae.

## Qué se sabe y qué no del 403 del 9/11
El primer intento fue una petición sin la cabecera `federation` y con un identificador de cliente inventado. El 403 es compatible con (a) la falta de esa cabecera de enrutado, (b) un `clientId` que el servidor no ha emitido, o (c) un control deliberado para la web de la federación. **Esta lectura no distingue entre ellas**.

## El sondeo (10/11/2026, 12:14 hora local, autorizado por el usuario): 403
Una sola petición, la que haría la web: `GET /fbcyl/streaming/register/fbcyl-23958/client-<uuid>` con `Accept: text/event-stream` y la cabecera `federation: fbcyl`, **sin `Origin`, `Referer` ni el JWT**, contra un partido ya jugado (el del 7/11; el REST de un partido terminado no trae `visibility`, así que el `clientId` fue uno generado, como hace la web cuando el servidor no da ninguno). Respuesta: **HTTP 403, cuerpo vacío, 0,2 s**, con las cabeceras de un filtro de seguridad de servidor (`Cache-Control: no-store`, `X-Frame-Options: DENY`, `X-XSS-Protection: 0`).

- **Descartado**: que el 403 fuera solo la cabecera `federation` que faltaba (la ruta ya lleva `/fbcyl/` y con la cabecera sigue igual).
- **Sigue abierto**: que el servidor exija un `clientId` **emitido por él** (`visibility.pushClientId` de la lectura inicial de un partido **en directo**, que un partido terminado no tiene) o que sea un control deliberado de la web. Con un partido jugado no se puede distinguir.
- **No se hace más**: probar `Origin`/`Referer` o usar el JWT de la página sería saltarse el control (decisión de #805), y no se hará.

## Qué sigue
1. **Sin peticiones nuevas**: el grabador del **15/11** guarda los cuerpos del REST que cambian; después del partido se mira si traen `visibility.pushClientId`. Es una lectura de nuestros datos, no un sondeo.
2. **Si el REST en directo no trae ese valor**, no hay forma legítima de registrar un cliente: se pregunta a la FBCyl por un acceso para clientes externos y #805 se cierra como «no procede».
3. **Si lo trae**, quedaría un único sondeo más con ese valor durante el partido (requiere confirmar con el usuario), y solo si responde se mediría la cadencia contra el REST.
4. **Mientras tanto** el REST de #446 sirve: un bloque de movimientos cada ~1 min (informe del 9/11).

## Cómo se obtuvo
`curl` con un agente identificado como investigación sobre páginas públicas; los ficheros se guardaron en un directorio aparte y se leyeron con `python -I`. No se ejecutó código del bundle ni se usó el JWT.
