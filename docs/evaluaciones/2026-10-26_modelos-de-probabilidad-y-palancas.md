# Estudio de modelos: ¿más estadística mejora la probabilidad de victoria y las palancas? (26/10/2026)

Responde a #567 (feedback de la 0.4.0: «en las palancas de probabilidad de victoria me gustaría incluir toda la información estadística de la que podamos disponer: básicas, avanzadas, pbp, propia, rival, equipo, individual; no sé si nuestro modelo lo permite o deberíamos investigar otros modelos»). Continúa [2026-10-22_reevaluacion-2026-27.md](2026-10-22_reevaluacion-2026-27.md).

## Resumen
1. **Más información de equipo no mejora la predicción.** Con **1.610 partidos** (22.351 cortes cada 5 min, desde los dos lados, validación cruzada **por partido**), un modelo que lee el marcador, el reloj, el valor previo y **toda** la estadística del partido (cuatro factores de ambos equipos, ritmo, eficiencia por posesión, faltas, tiempos muertos, últimos 5 min) tiene un log loss de **0,3916**, igual que el modelo con solo marcador, reloj y valor previo (**0,3914**) y peor que «solo valor previo» (0,3918 → 0,3938 con los cuatro factores del modelo actual). Unos árboles potenciados con las mismas variables empeoran (0,3934) y se descalibran (hasta 3,8 pp por decil).
2. **Lo que pasa en el partido tampoco predice lo que pasará después.** El margen de los **5 minutos siguientes** (15.930 tramos) se explica en un 7,1 % solo con valor previo, campo y marcador; añadir los factores de los últimos 5 min o de todo el partido **no sube ese R²** (0,0711 y 0,0709) y los coeficientes son ≈ 0 (±0,1 puntos por desviación típica sobre un objetivo de ±6). Un déficit de tiro, de balón o de rebote en el partido es, en promedio, **ruido que se corrige solo**, no una tendencia.
3. **Consecuencia para las palancas**: son una buena **descripción de lo que ha pasado** (dónde se están perdiendo puntos respecto al rival) pero **no hay evidencia de que corregirlas cambie la probabilidad de ganar** como dicen hoy los mensajes («+N % si vuelve a su nivel habitual», «+2 % de victoria» del control de ritmo). Propuesta: quitar esas cifras de los avisos y presentarlas como diagnóstico.
4. **Partir las palancas en ataque y defensa no mejora la predicción** (experimento 2b: el mismo R² de 0,071 y coeficientes simétricos de ±0,03). Sí es útil para el **staff**: dice dónde actuar (el rival acierta mucho: defensa; nosotros fallamos: ataque), aunque no prediga.
5. **El jugador sí aporta, y es lo único que aporta** (experimento 3): la calidad de los **quintetos en pista** (rating individual ajustado, tipo RAPM, calculado con partidos anteriores) predice el margen de los 5 minutos siguientes con un coeficiente de **+0,52 puntos por desviación típica** (intervalo 95 %: +0,35 a +0,71) y sube el R² de 0,088 a 0,094; con los ratings de la **temporada anterior** además, de 0,097 a **0,109** (+12 % relativo). En probabilidad de ganar la mejora es de 0,0016 de log loss y **no es distinguible del ruido** (−0,0009 a +0,0037). Los ratings son todavía muy ruidosos (fiabilidad par/impar 0,05-0,21): con más datos (varias temporadas) mejorarán.
6. **Dónde más margen hay**: el **valor previo** de los equipos (el ajuste por rival da +0,0006 de log loss) y los **ratings de jugador con varias temporadas**.
7. **El modelo actual no necesita sustituirse**: es tan bueno como cualquiera de los probados (A 0,3938 frente a un óptimo de 0,3908) y está calibrado.

## Qué información hay
| Momento | Fuente | Qué contiene |
|---|---|---|
| Antes del partido | Paquete (`baselines`) | `net_rtg_prior` y ritmo de cada equipo, prior de los cuatro factores (diferencia), medias de liga, `fg3_rate`, impacto por 40 min de la liga |
| Antes del partido | Paquete (tablas) | Perfil de temporada de cada jugador propio y rival (`players`, `rival_players`), quintetos de la temporada (`lineups`), zonas de tiro (`zones`), roles |
| Durante el partido | Snapshot del motor | Marcador, reloj, estadística de equipo (`fg2/fg3/ft/orb/drb/tov/stl/ast/blk/pts`), de cada jugador (puntos, faltas, minutos, tiempo seguido en pista, +/−), quinteto en pista y su balance, tiempos muertos, faltas por periodo |
| Durante el partido | Registro de eventos (`log`) | Cada canasta, tiro, pérdida, rebote, falta, tiempo muerto con su segundo; de ahí salen los parciales, sequías, origen de los puntos (`pbp`) y posesiones |
| Durante el partido | Tiros (`ShotChart`) | Zona de cada tiro: calidad de tiro |

## Experimento 1: ¿qué modelo predice mejor el resultado?
Cortes cada 5 min de 1.610 partidos (LF Endesa 2024-25, LF2 2024-25, LF Challenge 2024-25 y los 81 partidos de 2026/27 con ≥ 3 previos), cada lado de cada partido; los dos lados de un partido van siempre en el mismo grupo de la validación cruzada (5 grupos).

| Modelo | Log loss | Brier | Mayor desvío por decil (≥ 400 cortes) |
|---|---|---|---|
| A. Modelo de la app (estructural, valor previo + cuatro factores) | 0,3938 | 0,1283 | 1,6 pp |
| B. Solo valor previo | 0,3918 | 0,1274 | 1,4 pp |
| C. Solo marcador y tiempo | 0,4370 | 0,1451 | 1,6 pp |
| D. Logística: marcador, tiempo y valor previo | 0,3914 | 0,1275 | 1,0 pp |
| **G. Logística: marcador, tiempo y valor previo ajustado por rival (ridge)** | **0,3908** | **0,1272** | 0,9 pp |
| H. Logística: los dos valores previos | 0,3911 | 0,1273 | 1,0 pp |
| E. Logística: **toda la información** | 0,3916 | 0,1275 | 1,9 pp |
| F. Árboles potenciados: toda la información | 0,3934 | 0,1286 | 3,8 pp |

Por tramo del partido (log loss): en los primeros 10 minutos el valor previo importa (B 0,499 frente a C 0,603); en los últimos 10 el marcador lo decide todo (todos ≈ 0,27) y la información extra no aporta en ningún tramo.

Peso de cada grupo en la logística con toda la información (suma de |coeficiente tipificado|): marcador y tiempo 2,78 · valor previo 1,30 · faltas y tiempos muertos 0,46 · rebote ofensivo 0,13 · eficiencia por posesión 0,12 · racha de 5 min 0,11 · tiro 0,08 · tiros libres 0,08 · pérdidas 0,02 · ritmo 0,03. En los árboles (importancia por permutación): marcador 0,236 · valor previo 0,153 · tiro 0,008 · resto < 0,004. *Las faltas salen con signo contrario al esperado (más faltas propias, más probabilidad de ganar): es confusión (el que va por delante tiene menos prisa y más tiempo de faltas) y no debe leerse como causa.*

## Experimento 2: ¿persiste lo que se ve en el partido?
Objetivo: puntos de margen que gana el equipo en los 5 minutos siguientes a un corte (15.930 tramos). Se prueba si los factores de los 5 minutos anteriores o de todo el partido hasta ese momento añaden algo al valor previo, el campo y el marcador.

| Variables | R² (validación cruzada por partido) |
|---|---|
| valor previo + campo + marcador | 0,0714 |
| + factores de los 5 min anteriores | 0,0711 |
| + factores de todo el partido | 0,0709 |
| todo | 0,0705 |

Coeficientes tipificados (puntos en 5 min por desviación típica): valor previo +1,42 · campo +0,40 · marcador −0,08 · factores de 5 min: tiro +0,08, pérdidas −0,04, rebote +0,02, tiros libres −0,12 · factores del partido: tiro −0,17, resto ≈ 0. El del tiro cambia de signo entre la ventana corta y la larga: es regresión a la media, no tendencia.

### Experimento 2b: ¿ataque y defensa por separado?
Mismo objetivo, partiendo los factores de los 5 minutos anteriores en lo que hizo **nuestro ataque** y lo que hizo **el ataque del rival** (= nuestra defensa), en lugar de la diferencia.

| Variables | R² |
|---|---|
| valor previo + campo + marcador | 0,0714 |
| + diferencia de los cuatro factores (5 min) | 0,0711 |
| + ataque y defensa por separado (5 min) | 0,0711 |

Coeficientes: ataque (tiro +0,03, pérdidas +0,01, rebote +0,01, tiros libres −0,04) y defensa (tiro −0,03, pérdidas −0,02, rebote −0,01, tiros libres +0,05): simétricos y ≈ 0. Ni el ataque ni la defensa del rato anterior dicen nada del siguiente.

## Experimento 3: jugador y quinteto
**Método.** Cada partido se repite desde cero con el motor y se guarda quién está en pista cada 30 s y el margen que gana el local (≈ 15.000 tramos por competición y temporada, 6 carpetas de LF Endesa, LF2 y LF Challenge 2024-25 más los 235 partidos de 2026/27). Con el **60 % más antiguo** de partidos de cada temporada se calcula el **rating de cada jugador** (plus-minus ajustado con regularización ridge: puntos por 40 min respecto al jugador medio, descontando compañeros y rivales en pista). Con el **40 % posterior** (744 partidos que los ratings no han visto) se mide si la calidad de los dos quintetos en pista en cada corte predice el margen de los 5 minutos siguientes y el resultado.

**Fiabilidad de los ratings** (correlación entre los calculados con los partidos pares y los impares del tramo de entrenamiento): +0,15 / +0,05 (LF Endesa 2024/2025), +0,21 / +0,08 (LF2), +0,13 / +0,09 (LF Challenge) y −0,03 en 2026/27 (pocos partidos por jugador). Son ratings **muy ruidosos**: una temporada de una liga no da para distinguir bien a las jugadoras.

**Margen de los 5 minutos siguientes** (R², validación cruzada por partido, 8.837 tramos):

| Variables | R² |
|---|---|
| valor previo + campo + marcador (equipo) | 0,0884 |
| + calidad de los quintetos en pista (propio − rival) | 0,0944 |
| + los dos quintetos por separado | 0,0944 |

Coeficiente tipificado del quinteto propio − rival: **+0,521** (IC 95 % por partidos: +0,347 a +0,707), frente a +1,31 del valor previo y +0,47 del campo: **es significativo** y vale un tercio del valor previo del equipo.

**Con la temporada anterior** (4.054 tramos de las carpetas de 2025, ratings con la temporada 2024 completa de la misma competición y el 60 % antiguo de la actual; las jugadoras son en buena parte las mismas):

| Variables | R² |
|---|---|
| equipo | 0,0973 |
| + quintetos con ratings de la temporada actual | 0,1029 |
| + quintetos con ratings que incluyen la temporada anterior | **0,1085** |

**Probabilidad de ganar** (log loss): 0,4223 sin los quintetos y 0,4208 con ellos; mejora de +0,0016 con intervalo 95 % de −0,0009 a +0,0037 (no distinguible del ruido).

**Lectura**: a diferencia de la estadística de equipo, la **calidad de las jugadoras en pista sí predice lo que viene**, y mejora cuanto más datos tiene el rating. Es la base de palancas **individuales** accionables (quién debería estar en pista: «el quinteto actual es 3 puntos por 40 min peor que el mejor disponible») y de una mejora pequeña de la probabilidad. Con ratings más fiables (varias temporadas, o partiendo de la estadística individual de la plantilla como valor previo del rating) la señal debería crecer; con los de una sola temporada es modesta.

## Qué recomiendo (decisiones para el usuario)
1. **No sustituir el modelo**: ningún modelo más rico lo mejora con estos datos. Tampoco hace falta un modelo de caja negra: los árboles empeoran y descalibran.
2. **Quitar de los avisos las cifras causales** («+N % de victoria si vuelve a su nivel habitual» de `win_flip`, «+N % de victoria» de `pace_control`): no están respaldadas (experimento 2). Dejar la palanca como **diagnóstico** («el rival acierta el 75 % y nosotros el 60 %: nos cuesta unos 12 puntos cada 100 posesiones»), que sí es cierto de lo ocurrido.
3. **Partir las palancas en ataque y defensa** (lo que se pedía: «¿atacan bien?, ¿hay que mejorar la defensa?») **sin pretender predecir**: ataque = nuestro nivel frente a lo habitual de la liga, defensa = el del rival frente a lo habitual contra equipos como el nuestro. Requiere que el paquete lleve los cuatro factores de ataque y de defensa de la temporada de cada equipo (hoy solo lleva el prior de la *diferencia*): cambio de esquema del paquete (`schema_version`) y regenerar los publicados.
4. **Mejorar el valor previo con el ajuste por rival** (ridge): es lo único que sube la calidad (0,0006 de log loss; más con equipos con pocos partidos) y se calcula en el publicador sin tocar la app (cambia `net_rtg_prior`).
5. **Llevar el rating de jugador al paquete y a las alertas** (es lo único con señal): el publicador calcula el rating de cada jugadora con **varias temporadas** (RAPM con ridge, ≈ 10 min de cálculo por competición) y lo guarda en `players` (`rating`); el motor lo usa para (a) una palanca individual («el quinteto en pista rinde X por 40 min menos que el mejor disponible», que alimenta la rotación), (b) un pequeño ajuste de la probabilidad de victoria y (c) la propuesta de cambios. Medir antes con un test A/B sobre grabaciones reales. Cambia el esquema del paquete (`schema_version`).
6. **Después, probar la calidad de tiro por zona** (`ShotChart`: tiros abiertos frente a forzados, que persisten más que el porcentaje) y el tipo de posesión: no probados aún.

## Límites
- Los experimentos 1 y 2 son **estadística de equipo agregada**; el 3 usa ratings muy ruidosos de una o dos temporadas; la calidad de tiro por zona y el tipo de posesión no se han probado.
- Solo ligas femeninas de FEB con jugada a jugada y los partidos de 2026/27 disponibles; no se han probado FBCYL ni las ligas masculinas más allá de 2026/27.
- Los entrenadores **reaccionan** a lo que ven (tiempos muertos, cambios): una palanca que persistiría sin hacer nada puede desaparecer porque se corrige; el estudio mide el efecto neto, no el de actuar.
- Los cortes son cada 5 min y los dos lados de un partido son espejos: se agrupa por partido en la validación, pero las muestras efectivas son 1.610 partidos, no 22.351.

## Reproducir
`python scripts/wp_model_study.py collect --out samples.pkl <carpetas con los partidos de UNA temporada de UNA competición cada una>` (≈ 18 min para las 8 carpetas; usa `data/historical_games/*` y los partidos de 2026/27 exportados de Mongo), después `python scripts/wp_model_study.py fit samples.pkl` (experimento 1) y `python scripts/wp_model_study.py persistence samples.pkl` (experimento 2). `collect-lineups --out lineups.pkl <las mismas carpetas>` (≈ 8 min, 4 procesos) y `individual samples.pkl lineups.pkl` (experimento 3), y `persistence` incluye el 2b. Necesita scikit-learn y scipy.
