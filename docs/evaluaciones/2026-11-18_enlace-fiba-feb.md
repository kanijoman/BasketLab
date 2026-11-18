# Enlace FIBA ↔ FEB: medición con datos reales (#885)

Medido el 18/11/2026 sobre los 1.293 jugadores con minutos de los 356 partidos de FIBA ya cargados (`basketlab-archive-ext/fiba`, 1.136 con biografía: nacimiento y nacionalidad) y las plantillas de FEB 2022–2026 (`rosters/`, 4.634 fechas de nacimiento distintas, `person_id` anclado al `idPlayer`). Un jugador de FIBA se compara con los de FEB que **comparten fecha de nacimiento**, y entre ellos se mira cuántas palabras del nombre coinciden (sin acentos, mayúsculas; FIBA escribe «Nombre Apellido», FEB «NOMBRE APELLIDO1 APELLIDO2»).

## Resultado

| Grupo | Jugadores | Nacimiento + ≥ 2 palabras del nombre, único | Nacimiento + 1 palabra | Nacimiento solo (nombres distintos) | Sin nacimiento en FEB |
|---|---|---|---|---|---|
| Nacionalidad ESP | 71 | **68 (95,8 %)** | 0 | 2 | 1 |
| Otras nacionalidades | 1.065 | **34** | 4 | 848 | 179 |

- **No hubo ningún caso ambiguo** con dos o más palabras del nombre: 0 jugadores de FIBA con dos candidatos de FEB.
- **La fecha de nacimiento sola no corrobora nada**: el 80 % de los extranjeros comparte fecha con alguien de FEB por casualidad (848 de 1.065). Enlazar por nacimiento solo habría fusionado personas distintas; lo que corrobora es nacimiento **y** nombre.
- Los 34 extranjeros enlazados son jugadores que de verdad juegan en la formación o la sénior de FEB (p. ej. letones y turcos en equipos españoles); es el caso que más interesa al scouting (lo que hacían con su selección antes de llegar).
- Los 2 españoles «solo nacimiento» son coincidencias de fecha con otra persona (nombres sin relación) y no deben enlazarse; el que no está en FEB es una jugadora que no aparece en las plantillas de 2022–2026.

## Regla propuesta

1. **Enlace automático** (`linked`): misma fecha de nacimiento, **al menos dos palabras del nombre en común** y un único candidato.
2. **A revisión** (`review`): misma fecha y una sola palabra en común, o varios candidatos con dos palabras. 4 jugadores hoy.
3. **Nunca enlaza**: fecha de nacimiento sin coincidencia de nombre.

Limitaciones: FIBA solo trae biografía de los partidos cargados desde #975 (el refresco diario completa el resto); un jugador que no está en las plantillas de FEB de esas temporadas no puede enlazarse. FBCYL↔FEB sigue con la medición de la evaluación del 12/11 (clave exacta de inicial y dos apellidos: 25 únicas, 21 corroboradas por club, provincia o doble licencia, 4 a revisión), porque FBCYL no trae nacimiento.

## FBCYL ↔ FEB (#978)

FBCYL no trae fecha de nacimiento, así que el enlace es por **clave de nombre** (inicial del nombre y apellidos, sin partículas; la misma clave para `V. IBAÑEZ BARREIRO` y `VIRGINIA IBAÑEZ BARREIRO`, que son las dos formas en que se escribe) y **club**. Medido sobre el archivo completo (11.614 jugadores de FBCYL; las personas de las cajas de FEB, con todos los clubes en los que han estado):

| Resultado | Jugadores |
|---|---|
| `linked`: una única persona con esa clave y un club con ≥ 2 palabras en común con el de FBCYL | **352** |
| `review`: una única persona con esa clave pero otro club (cambio de club, selecciones autonómicas) | ≈ 1.600 |
| `review`: varias personas con esa clave | ≈ 130 |
| sin ninguna persona con esa clave en FEB | el resto (FBCYL es formación autonómica: la mayoría no llega a FEB) |

- Las palabras que tiene cualquier club (`BALONCESTO`, `CLUB`, `CB`, `ESCUELA`…) y las partículas no corroboran: sin quitarlas salían 442 enlaces, entre ellos clubes que solo compartían «BALONCESTO».
- Es deliberadamente prudente: un jugador que cambia de club (el caso normal de quien sube de cadete a júnior y a sénior) queda en `review` con su candidato, no enlazado. La cola de revisión (#980) es la que decide; lo que se enlaza solo es lo corroborado por el club.
- Un nombre de pila con varias palabras (`MARIA JOSE`) da otra clave que la forma de FEB con inicial: se pierde algún enlace, nunca se hace uno falso.
