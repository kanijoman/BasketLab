# FBCYL en directo: cómo abre la web de la FBCyl el canal SSE (#805, paso 1)

Parte de la épica #435 y sigue a [la evaluación del directo de FBCYL](2026-11-09_fbcyl-directo-go-no-go.md) (#444/#446). **Solo lectura**: se leyó el HTML público de `https://www.fbcyl.es/directos` y su bundle público `react/dist/main.js` (v0.3.17, 7,3 MB, minificado). **No se ha hecho ninguna petición al canal SSE** con cabeceras distintas de las del primer intento (403, 9/11/2026).

## Lo que hace la web
1. Carga la lectura inicial del partido por REST (`GET {streaming}/streaming/match-id/{adGameId}`, la misma que sondea nuestro grabador) y de ella toma `visibility.pushClientId` **si el servidor lo da**; si no, el navegador genera uno (`client-<crypto.randomUUID()>`).
2. Abre el canal con `EventSourcePolyfill` (el `EventSource` nativo no deja poner cabeceras) en `{streaming}/streaming/register/{conexión}/{clientId}` y **con una sola cabecera: `federation: fbcyl`**. El `{streaming}` es el mismo servicio de nuestro REST.
3. Al terminar el partido (calendario con `universallyid`) cierra el canal con `GET {streaming}/unregister/{conexión}/{sesión}` y redirige a las estadísticas.

## Qué dice de la credencial
- La cabecera `federation` es un **parámetro de enrutado del servicio**, que atiende a varias federaciones con el mismo servidor (la ruta REST lleva `/fbcyl/` en el camino; la de registro no): no es un secreto ni una identidad de navegador.
- El HTML de la página incrusta además un **JWT** (`data-jwt`, 15 minutos de vida, emitido por el servidor de la web). Los interceptores `Authorization: Bearer` del bundle son los de las llamadas del cliente REST de la web; **el canal SSE no los lleva**: sus cabeceras son solo las de `federation`. (El nombre minificado `Ra` podría sombrearse en otro módulo; con un bundle plano, como este, es improbable, pero no se ha ejecutado el código para comprobarlo.) Ese token **no se debe usar desde fuera**: está emitido a la sesión de la web de la federación.
- El `pushClientId` es el único valor que el servidor reparte para registrar un cliente. **No está en nuestras lecturas guardadas** (`fbcyl_streaming_20261107` solo conserva `readings` y `msstats`): no sabemos si el REST lo trae.

## Qué se sabe y qué no del 403 del 9/11
El primer intento fue una petición sin la cabecera `federation` y con un identificador de cliente inventado. El 403 es compatible con (a) la falta de esa cabecera de enrutado, (b) un `clientId` que el servidor no ha emitido, o (c) un control deliberado para la web de la federación. **Esta lectura no distingue entre ellas**.

## Decisión pendiente (del usuario)
Una sola petición de sondeo al canal **con `federation: fbcyl`** (y, si el REST de un partido en directo trae `visibility.pushClientId`, con ese valor) distinguiría (a) y (b) de (c). No imita `Origin` ni `Referer` —lo que #805 ya descartó—, pero es lo más cercano a lo que hace la web, así que no se envía sin que lo decida el usuario.

- **Si el canal responde**: se añade su captura al grabador **antes del 15/11** (Unileón–Raisan Eloy Villanueva) para medir cadencia y latencia contra el REST en el mismo partido; el criterio de #805 sigue siendo que baje de forma apreciable el sondeo de 10 s. Siguientes ocasiones: 22/11 y 6/12.
- **Si sigue dando 403**: se pregunta a la FBCyl por un acceso para clientes externos y se cierra #805 como «no procede».
- **Mientras tanto** el REST de #446 sirve: cada ~1 min un bloque de movimientos (informe del 9/11), que es lo que el staff ya tiene.

## Cómo se obtuvo
`curl` con un agente identificado como investigación sobre páginas públicas; los ficheros se guardaron en un directorio aparte y se leyeron con `python -I`. No se ejecutó código del bundle ni se usó el JWT.
