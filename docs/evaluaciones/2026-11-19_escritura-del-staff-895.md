# Escritura del staff en Talent: identidad, almacén y espacios (#895 / #154, F1)

Decisión del 19/11/2026 (usuario, con recomendación de Claude). Sin código: desbloquea F2 (#896, funciones y autenticación), F3 (#897, comentarios y seguimiento), F4 (#898, cola moderada de correcciones) y #980 (cola de revisión de enlaces). Parte de lo ya decidido: [#591](2026-10-28_acceso-y-reparto-591.md) (claves por alcance, sin cuentas) y [la evaluación de mercado](2026-11-12_mercado-scoutingfeb.md) (punto 9). El **disparador** de #591 «datos escritos por el usuario» se cumple, así que se reabren las cuentas **solo para Talent** y solo para escribir.

## Decisiones

| # | Punto | Decisión |
|---|---|---|
| 1 | Identidad | **OIDC externo, sin contraseñas propias.** Flujo de código con PKCE en una función de Vercel; sesión en cookie `HttpOnly`, `Secure`, `SameSite=Lax`, firmada y de caducidad corta. Persona = `sub` del proveedor (el email es atributo, no clave; solo se acepta con `email_verified`). |
| 2 | Proveedores | **Google** al empezar. Microsoft queda fuera hasta que un club lo pida (el código lee el proveedor del `iss`, así que añadirlo no cambia el modelo). |
| 3 | Almacén | **Base gestionada pequeña** (Marketplace de Vercel, región UE, plan gratuito), **aparte** del archivo de partidos y sin Atlas. El producto concreto se elige en F2 con tres criterios medibles: región UE, plan gratuito que cubra el volumen estimado (< 50 MB y < 100 usuarios) y exportación completa a JSON para la copia en frío. Cada colección lleva `club_id` y toda consulta lo filtra en el servidor. |
| 4 | Usuarios y aislamiento | **Espacio por club** y **tres roles por club**: `admin` (invita y quita personas del club), `analista` (lee y escribe) y `lector`. Aparte, **administrador del proyecto** (global, solo yo y quien yo designe): da de alta clubes y modera lo que es global. |
| 5 | Altas | Solo por **invitación** (el admin del club indica un email; al entrar con Google con ese email verificado se une al club). Nadie se auto-registra. El primer admin de cada club lo da de alta el administrador del proyecto. |
| 6 | Tablet (app live) | **Sin cambios**: los paquetes siguen abriéndose por alcance (#410); la app **no escribe** y no tiene cuentas. Si un día la tablet debe escribir, es otra decisión. |
| 7 | Lectura | **Sigue siendo estática** (`talent-data` sellada por alcance). La cuenta no abre datos de partidos: solo habilita escribir y leer lo escrito. Quitar a alguien de la escritura es inmediato; quitarle la lectura sigue siendo rotar el alcance (límite ya conocido de #591). |
| 8 | Lo global frente a lo del club | Comentarios, seguimiento y listas son **del club**. Una **corrección de identidad** (enlace FBCYL/FIBA↔FEB, #980) es un hecho sobre el mundo y afecta a todos: la **propone** cualquier `analista`, la **aplica** el administrador del proyecto (cola moderada, #898). |
| 9 | Determinismo | El pipeline nunca lee la base en caliente: una acción programada **exporta** las decisiones aplicadas a un fichero ordenado y sin marcas de tiempo en `basketlab-archive-ext` (`decisions/links.json`) y `run_identity_links.py` las aplica al regenerar (la decisión del staff gana siempre; repetir no cambia un byte). |
| 10 | Datos personales | El email y el `sub` son datos personales (RGPD/LOPDGDD): región UE, solo lo necesario, borrado al quitar a la persona, y las notas se conservan anónimas (`autor: eliminado`) si el club lo decide. |

## Matriz rol → operación

Las rutas son las que F2–F4 deberán crear (funciones de Vercel bajo `/api/talent/`); hoy no existe ninguna. `—` = prohibido; todo lo demás exige sesión válida y pertenecer al club de la fila.

| Operación | lector | analista | admin del club | admin del proyecto |
|---|---|---|---|---|
| `GET /session` (quién soy, mi club y rol) | sí | sí | sí | sí |
| Leer comentarios, seguimiento y listas del club | sí | sí | sí | sí (cualquier club) |
| Crear/editar/borrar **sus** comentarios | — | sí | sí | sí |
| Borrar comentarios de otras personas del club | — | — | sí | sí |
| Seguir o dejar de seguir a un jugador, listas del club | — | sí | sí | sí |
| Proponer una corrección de identidad | — | sí | sí | sí |
| Ver la cola de correcciones propuestas | — | sí (las del club) | sí (las del club) | sí (todas) |
| Aplicar o rechazar una corrección | — | — | — | sí |
| Invitar, cambiar rol o quitar personas del club | — | — | sí | sí |
| Alta de club, primer admin, cierre de club | — | — | — | sí |
| Exportar los datos del club | — | — | sí | sí |

## Invariantes (cada uno con su test en F2–F4)

1. Ninguna función lee ni escribe sin resolver primero **sesión → persona → pertenencia → rol**; sin sesión es 401, sin pertenencia o rol es 403, nunca 404 que revele existencia.
2. El `club_id` sale **siempre de la sesión**, nunca del cuerpo ni de la URL.
3. Un usuario de un club no lee, escribe ni deduce (por tiempos o errores) datos de otro.
4. Quitar a una persona invalida sus sesiones en la siguiente petición (la pertenencia se comprueba en la base, no solo en la cookie).
5. Una invitación caduca (7 días) y solo sirve para el email al que se envió.
6. El pipeline que consume las decisiones es puro y determinista (decisión 9).

## Fuera de alcance / pendiente

- Elegir el producto de base de datos concreto (F2) y medir que cabe en el plan gratuito.
- Cobro y niveles de pago: siguen en #591 (beta gratuita hasta la autorización de FEB).
- Auditoría: se guarda quién y cuándo de cada escritura; un visor de auditoría no se construye aún.
- Si Analytics (no Talent) necesitara cuentas, es otra decisión; esta solo cubre Talent.
