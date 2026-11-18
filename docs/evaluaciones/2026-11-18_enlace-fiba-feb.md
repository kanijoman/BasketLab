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
