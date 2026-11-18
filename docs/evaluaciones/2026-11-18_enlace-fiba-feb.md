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

FBCYL no trae fecha de nacimiento. Medido sobre el archivo completo (520 partidos de FBCYL de 2026/27; las personas de las cajas de FEB 2022–2026 con todos sus clubes, el sexo de sus competiciones según el catálogo y, de las plantillas de FEB, el nombre completo y la fecha de nacimiento de 8.676 de ellas).

**Quién es una jugadora de FBCYL**: su `uuid`. El `actorId` cambia en cada partido (11.614 `actorId` para **2.253 personas**); la primera versión del enlace contaba cada partido como una jugadora distinta y con un solo club. El repositorio ya usaba el `uuid` (`fbcyl_pipeline`).

**Cuánto se puede enlazar**: el 82 % de las personas de FBCYL **no tiene a nadie en FEB** con su clave de nombre (es formación y sénior autonómica: solo llega a FEB quien juega los campeonatos de España, una selección autonómica o una liga FEB). De ellas, 962 no se parecen a nadie, 604 comparten inicial y primer apellido con otra persona (otro segundo apellido: «LARA CONDE MATE» y «LAURA CONDE JIMENEZ») y 251 comparten los dos apellidos con otra inicial (hermanos, a veces de otro sexo). Ninguna de esas es un enlace perdido.

**Regla** (`src/market/identity_link`):

1. **Candidatos**: misma clave de nombre (inicial del nombre y apellidos **en su orden**, sin partículas ni las marcas de FBCYL como «(REF)» o «(JUN)»; la misma para `V. IBAÑEZ BARREIRO` y `VIRGINIA IBAÑEZ BARREIRO`), el mismo nombre completo de las plantillas de FEB, o los dos últimos apellidos cuando FBCYL escribe un nombre de pila compuesto («MARIA JOSE GARCIA LOPEZ» es «M. GARCIA LOPEZ»).
2. **No puede ser ella**: un candidato del otro sexo o **demasiado mayor para la categoría** en la que juega en FBCYL (un U16 de la temporada que empieza en S nació en S-15 o después, como en los campeonatos cadetes de FEB, donde el 99 % tiene 14 o 15 años; un año de margen; un sénior solo pide 13 años). En la primera medición 45 personas solo tenían candidatos así, y entre los enlazados por club había una U16 «corroborada por el club» que tenía 17 años: dos hermanas con la misma inicial en el mismo club.
3. **Enlace** (`linked`) con un único candidato y una prueba: **el club** (2 palabras en común que no sean genéricas como `BALONCESTO` o `CLUB`, o todas las de uno de los dos nombres: «BALONCESTO LA FLECHA» con «BALONCESTO LA FLECHA») o **el nombre completo con un nacimiento que encaje en la categoría**, salvo que FEB tenga ese nombre completo en personas con otra fecha de nacimiento (homónimos: de 27 nombres repetidos en las plantillas, 21 son la misma persona con dos ids de FEB y 6 son personas distintas, como dos «MARIA GARCIA RODRIGUEZ» de 2008).
4. **A revisión** (`review`): varios candidatos, o uno sin prueba.

| Resultado (2.253 personas de FBCYL) | Primera versión | Ahora |
|---|---|---|
| `linked` por club | 68 | **106** |
| `linked` por nombre completo y nacimiento | — | **128** (63 en categorías de formación, 65 en sénior) |
| `review` | 123 (1.732 entradas de partido) | **110** (99 con un candidato sin prueba, 11 con varios) |
| solo con candidatos de otro sexo o demasiado mayores | (contaban como candidatos) | 29 |

- Las muestras de los enlaces nuevos son coherentes en ciudad y edad (Valladolid con Valladolid, León con León, la selección de Castilla y León); en sénior, «encaja en la categoría» solo pide ser mayor de 13, así que ahí la prueba es el nombre completo, único en FEB y del mismo sexo.
- **Opción no aplicada**: 83 de los que quedan en revisión tienen un par de apellidos que solo lleva una persona en cada lado (ALDECOA LÓPEZ, FERNANDEZ-TRESGUERRES MUÑOZ…) y casi todos parecen la misma persona; enlazarlos exigiría decidir cuándo un apellido es «raro» en una población que crece con cada temporada cargada. Se decide con el usuario.
