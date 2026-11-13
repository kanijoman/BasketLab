# Evaluación: formación en FBCYL y en FIBA (spike #915)

Parte de la épica #872 (Talent), tras la categoría explícita de #914 y #918 (U14 infantil, U15–U16 cadete, U17–U18 júnior; **U19–U22 son sénior**). Medido el 13/11/2026 con peticiones reales, de una en una y con pausa de 1 s, solo a páginas públicas y a los combos y flujos que el scraper de FBCYL ya usa. Sin credenciales.

**Veredicto.** **FBCYL: GO** para la formación **autonómica** (cadete, infantil y júnior): trae lo mismo que la sénior (estadística por jugador, minutos, coordenadas de tiro) y encaja en el formato canónico sin cambios. **FIBA: GO parcial**: las plantillas (nacimiento, altura en cm y en pies-pulgadas, posición, nacionalidad, club) y los líderes por competición son públicos y sirven ya; la **caja de cada partido** solo sale de una API que el navegador de FIBA llama con una clave propia, y usarla es una decisión (ver «Decisiones»).

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
- **Caja por partido**: la ficha de cada partido (`/games/<gameId>`) trae el listado con `gameId` y marcador, pero la **estadística por jugador y la jugada a jugada se cargan desde `digital-api.fiba.basketball` con una clave de suscripción que la propia página incrusta para su navegador**. No se ha usado. Sin ella, de FIBA formación hay plantilla y líderes, no caja.

## Decisiones (del usuario)

1. **¿Se usa la API de FIBA con la clave de su web?** Es una credencial del cliente web de FIBA, no una página pública: la épica da por buena la cuestión legal de leer lo público, y esto es otra cosa. Sin ella, FIBA aporta plantillas y líderes. Con ella, caja y jugada a jugada de 2024 en adelante.
2. **¿Se carga la formación provincial y escolar de FBCYL?** Propuesta: **autonómica primero** (cadete, infantil, júnior); provincial y escolar después, si hace falta, como tandas aparte (el principio de la épica es no descartar datos, publicación por niveles).
3. **¿Infantil de FBCYL?** Entra con la advertencia de que la mitad no trae minutos: sin minutos no hay tasas por 40 ni percentiles (`eligible` de Talent).

## Qué implica para las épicas

- **Catálogo** (`config/competitions.json`): las entradas de FBCYL de formación llevarán `category: formacion`, `age_group` (`U14` infantil, `U16` cadete, `U18` júnior) y `label`, como las de FEB (#914). El catálogo ya valida la edad.
- **#885 (D1, enlace FBCYL↔FEB)**: es más necesario con formación (un jugador sube de cadete a júnior y a sénior sin id común); la corroboración será por nombre y año de nacimiento, que FBCYL no trae: la fecha solo estará en el lado FEB.
- **#887 (D3, FIBA)**: arrancar con **plantillas** (nacimiento, altura, posición) y líderes, que son públicos y rellenan huecos de FEB (#910); la caja espera a la decisión 1. U20 y U19 entran como sénior, **no** como formación.
- **Selector**: FBCYL tendrá nivel Categoría (Sénior / Formación) bajo su ámbito, sin cambios en el selector.

## Límites de esta evaluación

- FBCYL: **solo se midieron las tres últimas temporadas** y el territorial `0` (todos); una muestra de 12 grupos de 7 categorías para la estadística por partido.
- FIBA: sin archivo antiguo, sin divisiones B y C, sin U17 y sin caja por partido.
- Los **volúmenes** de partidos son estimados, no contados.
- No se midió el tiempo real de una carga completa (quedan las tandas del refresco de FEB como referencia, 90 min por ejecución).
