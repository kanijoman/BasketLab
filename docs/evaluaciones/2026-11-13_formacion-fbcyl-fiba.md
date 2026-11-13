# Evaluación: formación en FBCYL y en FIBA (spike #915)

Parte de la épica #872 (Talent), tras la categoría explícita de #914 y #918 (U14 infantil, U15–U16 cadete, U17–U18 júnior; **U19–U22 son sénior**). Medido el 13/11/2026 con peticiones reales, de una en una y con pausa de 1 s, solo a páginas públicas y a los combos y flujos que el scraper de FBCYL ya usa. Sin credenciales.

**Veredicto.** **FBCYL: GO** para la formación **autonómica** (cadete, infantil y júnior): trae lo mismo que la sénior (estadística por jugador, minutos, coordenadas de tiro) y encaja en el formato canónico sin cambios. **FIBA: GO**: las plantillas (nacimiento, altura en cm y en pies-pulgadas, posición, nacionalidad, club), los líderes y, **tras la decisión del usuario de probar la clave, también la caja por partido**. Resultado: la jugada a jugada completa de cada partido terminado viene en el HTML público de su ficha, **sin clave**, y reproduce la API al detalle; la clave solo añade los minutos y no hace falta para lo demás (ver «Caja por partido»).

## FBCYL

Los combos de fbcyl.es (`combo_categories2` y `combo_competicions2`, los del scraper) listan por temporada, género y territorial. Temporadas publicadas: 2016/17 a 2026/27. Medidas las **tres últimas** (137 combinaciones temporada–género–categoría).

**Hay mucha formación, en tres niveles.** Categorías y grupos de competición por temporada (cadete + infantil + júnior; minibásket y menores aparte):

| Nivel | 2026/27 (en curso) | 2025/26 | 2024/25 |
|---|---|---|---|
| **Autonómico** (1ª y 2ª División, Liga UEMC Júnior) | 12 cat. / 52 grupos | 12 cat. / 89 grupos | 12 cat. / 108 grupos |
| Provincial | 5 cat. / 11 grupos | 6 cat. / 38 grupos | 6 cat. / 60 grupos |
| Escolar | 5 cat. / 7 grupos | 8 cat. / 21 grupos | 5 cat. / 14 grupos |

Las 12 categorías autonómicas de 2026 (id de categoría; **cambia cada temporada**): 1ª Div. cadete F `1126` / M `1131`; 1ª Div. infantil F `1127` / M `1133`; Liga UEMC júnior F `1130` / M `1132`; 2ª Div. júnior F `1137` / M `1138`; 2ª Div. cadete F `1135` / M `1141`; 2ª Div. infantil F `1136` / M `1142`. Aparte: minibásket autonómico (`1139`, `1140`) y la Liga 3x3 (`1180`).

**Lo que trae cada partido** (`getJsonWithMatchStats`, el mismo flujo que la sénior). Muestra: 12 grupos de 6 competiciones autonómicas de formación, más la Primera Nacional Femenina (sénior) como control:

| Competición | Partidos con estadística | Jugadores con minutos | Partidos con coordenadas de tiro |
|---|---|---|---|
| Sénior 1ª Div. Fem. A-1 (control) | 8 de 8 | 176 de 177 | 8 de 8 |
| Júnior Fem. UEMC (2 grupos) | 7 de 9 | 151 de 151 | 7 de 7 |
| Cadete Fem. 1ª Div. | 3 de 3 | 72 de 72 | 3 de 3 |
| **Infantil Fem. 1ª Div.** | 3 de 3 | **24 de 46** | **1 de 3** |
| Júnior Masc. UEMC | 3 de 3 | 68 de 71 | 3 de 3 |
| Minibásket Masc. | 8 de 8 | 182 de 182 | 8 de 8 |

- **Cadete y júnior igualan a la sénior.** **Infantil es irregular**: la mitad de los jugadores sin minutos y 2 de 3 partidos sin tiros situados (una muestra pequeña, a confirmar al cargarla).
- **Los minutos** están en `timePlayed` **del jugador**, no dentro de `data` (error de lectura mío al principio, comprobado contra la sénior).
- **Sin biografía**: FBCYL no tiene plantillas (lo mismo que la sénior, #885): la identidad es el `uuid` (`fbcyl:<uuid>`) y no hay nacimiento, altura ni posición.
- **Volumen** (estimación con la muestra: 2 a 28 partidos por grupo, mediana 3): del orden de **varios cientos de partidos por temporada** en cadete, infantil y júnior autonómicos. Mucho menos que un campeonato de España de formación de FEB.
- **Mapa de edades**: infantil → `U14`, cadete → `U16`, júnior → `U18`. Minibásket, benjamín, alevín y premini quedan **fuera de la tabla** (menores de 12): no llevan `age_group`.

## FIBA

Eventos de formación con página pública de estadísticas, sondeados por nombre de evento (2014–2026, 92 direcciones):

| Evento | Categoría (#918) | Años con página |
|---|---|---|
| U16 EuroBasket, masculino y femenino | formación, cadete (`U16`) | 2024, 2025, 2026 |
| U18 EuroBasket, masculino y femenino | formación, júnior (`U18`) | 2024, 2025, 2026 |
| U20 EuroBasket, masculino y femenino | **sénior** (U19–U22) | 2024, 2025, 2026 |
| U19 Copa del Mundo, masculina y femenina | **sénior** | 2025 |

- **Solo desde 2024** en la web actual: de 2014 a 2023 todas dan «Page Not Found». **No se ha mirado** el archivo antiguo de FIBA ni las divisiones B y C (existen: `…-division-b`, `…-division-c`), ni el U17 de la Copa del Mundo (no apareció con el nombre esperado).
- **Plantillas públicas** (`/teams/<país>`, renderizadas en el servidor): `personId`, nombre, nacimiento, altura en cm **y en pies-pulgadas**, posición, nacionalidad, club y partidos jugados. Muestra (U18 EuroBasket 2025, Austria, 14 jugadores): nacimiento 14/14, altura 11/14, posición 7/14, club 10/14. La posición viene en inglés («Point Guard», «Shooting Guard», «Power Forward», **«Guard»**, **«Forward»**): `canonical_position` y `position_group` de #910 la cubren (las dos últimas solo dan grupo G/F). **Es el caso que motivó la altura en pies-pulgadas y la fusión campo a campo de #910.**
- **Líderes públicos** (`/stats`): tabla de 50 jugadores por evento (puntos, rebotes…), no la lista completa ni por partido.
- **Caja por partido: dos caminos, y el público basta.** Medido sobre U18 EuroBasket 2025 (Austria–Francia, partido 125809):
  - **Jugada a jugada pública** (en el HTML de `/games/<gameId>`, partidos terminados, sin clave): 598 eventos con `ac` (`P2`, `P3`, `FT`, `REB`, `ASS`, `TO`, `ST`, `BS`, `FOUL`, `RFOUL`, `SUBST`, `JB`…), el texto («3pt jump shot made», «Free throw made 1 of 2»), el marcador, el reloj y el `pId` del jugador. Es el mismo tipo de dato que el play-by-play de FEB: la caja se calcula con nuestro parser, **asistencias, robos, pérdidas, tapones y faltas incluidos**.
  - **API de FIBA** (`digital-api.fiba.basketball`, cabecera `OCP-APIM-SUBSCRIPTION-KEY` con la clave que su página da a cada navegador): por jugador y partido da **minutos** (`playDurationInSeconds`), puntos, tiros (2, 3, libres) y rebotes, **pero no asistencias, robos, pérdidas, tapones ni faltas** por partido (solo en el acumulado). Se probó con la clave leída de la página en el momento (nunca guardada): 3 llamadas, todas 200.
  - **Validación**: para un jugador y partido (Strobl, 125809) la jugada a jugada da 9 triples intentados y 2 anotados, 1 de 2 en dobles, 4 de 4 en libres, 3 rebotes defensivos y 12 puntos, **exactamente lo que da la API**.
  - **Lo que falta**: los **minutos** (la API los da; de la jugada a jugada salen de las sustituciones, que necesitan el quinteto inicial, aún sin medir) y una **comprobación sobre más partidos**.
  - **Cuidado**: la ficha del partido a veces devuelve una versión genérica sin datos (visto 2 veces en ~10 peticiones): el cliente debe **reintentar** y comprobar que trae `playByPlay`. Las posiciones de la jugada a jugada son códigos cortos (`PG`, `SG`, `PF`, `C`, `G`, `F`), distintos de los nombres de la plantilla.

## Decisiones (del usuario)

1. **La clave de FIBA: decidido (13/11/2026), se probó.** Funciona, pero **la caja no depende de ella** (la jugada a jugada es pública). Propuesta: **no depender de la clave** en la carga: es una credencial del cliente web de FIBA que puede rotar; se usaría, como mucho, para los minutos, leyéndola de la página en cada ejecución y sin guardarla en el repositorio ni en los secretos.
2. **FBCYL: decidido (13/11/2026)**: **solo competiciones autonómicas de cadete hacia arriba y sénior, masculino y femenino**. **Fuera**: infantil, provincial, escolar, minibásket y menores. Se anota que el archivo completo (principio de la épica: no descartar datos) queda sin cargar por esa decisión.

## Qué implica para las épicas

- **Catálogo** (`config/competitions.json`): las entradas de FBCYL de formación llevarán `category: formacion`, `age_group` (`U14` infantil, `U16` cadete, `U18` júnior) y `label`, como las de FEB (#914). El catálogo ya valida la edad.
- **#885 (D1, enlace FBCYL↔FEB)**: es más necesario con formación (un jugador sube de cadete a júnior y a sénior sin id común); la corroboración será por nombre y año de nacimiento, que FBCYL no trae: la fecha solo estará en el lado FEB.
- **#887 (D3, FIBA)**: **plantillas** (nacimiento, altura, posición), líderes y **caja por partido desde la jugada a jugada pública**, que rellenan huecos de FEB (#910); la clave solo para minutos y sin depender de ella. U20 y U19 entran como sénior, **no** como formación.
- **Selector**: FBCYL tendrá nivel Categoría (Sénior / Formación) bajo su ámbito, sin cambios en el selector.

## Límites de esta evaluación

- FBCYL: **solo se midieron las tres últimas temporadas** y el territorial `0` (todos); una muestra de 12 grupos de 7 categorías para la estadística por partido.
- FIBA: sin archivo antiguo, sin divisiones B y C, sin U17; la caja se validó con **un** jugador y partido, y los minutos desde la jugada a jugada no se han medido.
- Los **volúmenes** de partidos son estimados, no contados.
- No se midió el tiempo real de una carga completa (quedan las tandas del refresco de FEB como referencia, 90 min por ejecución).
