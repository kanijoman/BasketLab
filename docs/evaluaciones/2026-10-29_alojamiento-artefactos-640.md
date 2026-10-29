# Local-first: alojamiento de los artefactos de la web (#640)

Decide dónde se publican las filas del contrato (#328) y los informes sellados (#638) y cómo se actualizan. Parte de la épica #326, tras el GO de [#327](2026-10-29_local-first-p0-go-no-go.md).

## Decisión

1. **Ahora (beta gratuita): rama `web-data` del propio repositorio**, servida por `raw.githubusercontent.com`, igual que `live-packages` para la app. Cero infraestructura nueva, CORS abierto, ya probado en producción.
2. **El contrato no depende del anfitrión**: `index.json` (manifiesto corto) + ficheros con el hash del contenido en el nombre (inmutables). La web lee una **URL base configurable** (`VITE_DATA_BASE`); cambiar de anfitrión es publicar lo mismo en otro sitio y cambiar esa variable.
3. **Antes de cobrar (#637) se migra a un anfitrión estático con SLA y términos comerciales** (Cloudflare Pages/R2 o Vercel Pro; se decide entonces con precios reales). No se hace ahora: no aporta nada a la beta.
4. **Vercel Hobby queda descartado para los datos**: sus términos son de uso personal no comercial (se cobrará), cada refresco sería un despliegue (3 al día, mezclados con los del front) y exigiría un token de Vercel en Actions.

## Medición (29/10/2026, desde el PC del autor; una red, una hora: orientativa)

| Anfitrión | Fichero | Latencia | Caché |
|---|---|---|---|
| `raw.githubusercontent.com` (rama `live-packages`) | `index.json`, 41 KB | 0,10–1,27 s (3 intentos) | `max-age=300`, ETag, `access-control-allow-origin: *` |
| ídem | paquete de 140 KB comprimidos | mediana ≈ 0,5 s; 0,20–0,80 s en 7 de 8; una cola de 2,8 s | ídem |
| Vercel (`basket-lab.vercel.app`) | `index.html`, 917 B | 0,17–0,59 s | `max-age=0, must-revalidate`, `x-vercel-cache: HIT`, brotli |

Lectura: los dos son del mismo orden (décimas de segundo); GitHub tiene más cola. Un paquete de temporada de lectura son ≈ 0,3 MB, así que la red cuesta ≈ 0,3–1 s en una visita fría y nada después. **No se mide la capacidad de carga** (muchos usuarios a la vez): `raw` no publica límites ni SLA, que es la razón de la migración del punto 3, no un problema de la beta.

## Política de actualización y versiones

- **Refrescos**: 3 al día (`atlas-refresh`: 05:30, 13:30 y 21:30 UTC); tras él se exportan filas e informes y se publica `web-data`. Sin partidos nuevos no cambia ningún byte (el exportador ya es determinista), así que el commit se omite.
- **Caché**: el manifiesto caduca a los 5 minutos de `raw` (aceptable para 3 refrescos al día); los ficheros llevan el hash en el nombre y se piden por el manifiesto, así que nunca se sirve una mezcla de versiones.
- **Versión del contrato**: `schema` en el manifiesto. El cliente solo acepta los que conoce y, si no, vuelve a la API (mientras exista). Un cambio incompatible sube el número y se publican las dos versiones durante un ciclo; el cliente nuevo y el antiguo conviven.
- **Publicación**: como `live-packages` (`live-packages.yml`): se construye un directorio, se hace `git init` y **un solo commit con `push -f`** a la rama, así que el historial no crece. Un `push` es atómico: no hay estado intermedio entre manifiesto y ficheros. Consecuencia: los ficheros de la versión anterior desaparecen, y una pestaña abierta con el manifiesto viejo recibe 404; el cliente lo trata como «manifiesto caducado», lo vuelve a pedir y reintenta una vez (sin conservar versiones antiguas).
- **Guarda de Vercel**: la rama lleva `frontend/vercel.json` con `git.deploymentEnabled: false` (`VERCEL_GUARD` de `publisher.py`) para que la integración de Vercel no intente compilarla en cada publicación; `web-data` debe llevar la misma.

## Riesgos aceptados

- `raw` puede limitar o cambiar sin aviso: aceptable en beta, con la API como respaldo hasta P7 (#334).
- Los datos de FEB no pueden estar en claro en un sitio público (#637): la rama publica **solo contenido sellado** (informes, y las filas cuando se decida su nivel de acceso). El archivo de partidos en bruto va a un repositorio **privado** (#646), no aquí.
- Las filas del contrato hoy se exportan **sin sellar** a `frontend/public/local-data` (ignorado por git). Publicarlas en `web-data` exige decidir antes su alcance de acceso (abierto durante la beta, como los informes): se resuelve en #328 con `report_scopes`.
