# Estudio de modelos: ¿más estadística mejora la probabilidad de victoria y las palancas? (26/10/2026)

Responde a #567 (feedback de la 0.4.0: «en las palancas de probabilidad de victoria me gustaría incluir toda la información estadística de la que podamos disponer: básicas, avanzadas, pbp, propia, rival, equipo, individual; no sé si nuestro modelo lo permite o deberíamos investigar otros modelos»). Continúa [2026-10-22_reevaluacion-2026-27.md](2026-10-22_reevaluacion-2026-27.md).

## Resumen
1. **Más información de equipo no mejora la predicción.** Con **1.610 partidos** (22.351 cortes cada 5 min, desde los dos lados, validación cruzada **por partido**), un modelo que lee el marcador, el reloj, el valor previo y **toda** la estadística del partido (cuatro factores de ambos equipos, ritmo, eficiencia por posesión, faltas, tiempos muertos, últimos 5 min) tiene un log loss de **0,3916**, igual que el modelo con solo marcador, reloj y valor previo (**0,3914**) y peor que «solo valor previo» (0,3918 → 0,3938 con los cuatro factores del modelo actual). Unos árboles potenciados con las mismas variables empeoran (0,3934) y se descalibran (hasta 3,8 pp por decil).
2. **Lo que pasa en el partido tampoco predice lo que pasará después.** El margen de los **5 minutos siguientes** (15.930 tramos) se explica en un 7,1 % solo con valor previo, campo y marcador; añadir los factores de los últimos 5 min o de todo el partido **no sube ese R²** (0,0711 y 0,0709) y los coeficientes son ≈ 0 (±0,1 puntos por desviación típica sobre un objetivo de ±6). Un déficit de tiro, de balón o de rebote en el partido es, en promedio, **ruido que se corrige solo**, no una tendencia.
3. **Consecuencia para las palancas**: son una buena **descripción de lo que ha pasado** (dónde se están perdiendo puntos respecto al rival) pero **no hay evidencia de que corregirlas cambie la probabilidad de ganar** como dicen hoy los mensajes («+N % si vuelve a su nivel habitual», «+2 % de victoria» del control de ritmo). Propuesta: quitar esas cifras de los avisos y presentarlas como diagnóstico.
4. **Partir las palancas en ataque y defensa no mejora la predicción** (experimento 2b: el mismo R² de 0,071 y coeficientes simétricos de ±0,03). Sí es útil para el **staff**: dice dónde actuar (el rival acierta mucho: defensa; nosotros fallamos: ataque), aunque no prediga.
5. **El jugador sí aporta, y es lo único que aporta** (experimento 3): la calidad de los **quintetos en pista** (rating individual ajustado, tipo RAPM, calculado con partidos anteriores) predice el margen de los 5 minutos siguientes con un coeficiente de **+0,52 puntos por desviación típica** (intervalo 95 %: +0,35 a +0,71) y sube el R² de 0,088 a 0,094; con los ratings de la **temporada anterior** además, de 0,097 a **0,109** (+12 % relativo). En probabilidad de ganar la mejora es de 0,0016 de log loss y **no es distinguible del ruido** (−0,0009 a +0,0037). Los ratings son todavía muy ruidosos (fiabilidad par/impar 0,05-0,21): con más datos (varias temporadas) mejorarán.
6. **Otras familias de modelos no ganan** (experimento 4, 2.886 partidos con las ligas masculinas): logística, árboles potenciados y una red neuronal no superan al modelo de la app **bien calibrado**; la red neuronal es la peor. Las redes bayesianas (grafos discretos) y los modelos de secuencia no encajan con estos datos ni con el motor.
7. **El modelo actual no necesita sustituirse, pero sí recalibrarse**: en las ligas **masculinas** está descalibrado (log loss 0,4433, desvío de 3,3 pp; pide más dispersión y más ventaja de campo). **Calibrado por familia de competiciones y con un valor previo bayesiano dinámico** (Kalman dentro de la temporada) baja el log loss de 0,4158 a **0,4070** (−0,0088, IC 95 % −0,0120 a −0,0057): la mayor mejora de todo el estudio, sin cambiar la app ni el tamaño de los paquetes. Arrancar de la temporada anterior añade poco en esta medida (−0,0007).

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

### Experimento 3b: ligas masculinas, cadena de temporadas y estimador del rating (26/10/2026)
Mismo método con **Primera y Segunda FEB** de la base local (Primera 2024-25, 2025-26 y las 9 primeras jornadas de 2026/27; Segunda igual; 1.478 partidos, sin scrapear nada) y los ratings de **todas las temporadas anteriores** de la competición más el 60 % antiguo de la actual. Se prueba además la **regularización** del rating y un **valor previo a partir de la estadística individual** (puntos, asistencias, rebotes, robos, tapones, pérdidas, faltas, tiros por 40 min).

| Competición | Equipo (valor previo + campo + marcador) | + quintetos, temporada actual | + quintetos, con temporadas anteriores | Coeficiente del quinteto (IC 95 %) |
|---|---|---|---|---|
| Ligas femeninas (ridge 500) | 0,0973 | 0,1037 | **0,1105** | +0,46 (+0,31 a +0,64) |
| Ligas femeninas (ridge 2.000) | 0,0973 | 0,1029 | 0,1085 | +0,52 (+0,35 a +0,71) |
| Primera y Segunda FEB (ridge 2.000) | 0,0482 | 0,0531 | 0,0550 | +0,30 (+0,10 a +0,49) |
| Primera y Segunda FEB (ridge 8.000) | 0,0482 | 0,0547 | 0,0570 | +0,40 (+0,18 a +0,63) |
| Primera y Segunda FEB (ridge 30.000) | 0,0482 | 0,0546 | **0,0579** | +0,50 (+0,21 a +0,80) |

(R² del margen de los 5 minutos siguientes, validación cruzada por partido; 6.838 tramos de 571 partidos en las masculinas.)

- **La señal se repite en las ligas masculinas**, con menos fuerza (el valor previo del equipo explica menos y los ratings son aún más ruidosos: fiabilidad par/impar de 0,01 a 0,07).
- **Más temporadas siempre ayudan** (de +0,005 a +0,010 de R² extra), y **la regularización óptima depende de la competición**: poca para las femeninas (ridge 500-2.000), mucha para las masculinas (8.000-30.000), donde hay más jugadores y menos minutos por jugador. Hay que ajustarla **por competición con validación cruzada**, no fijarla.
- **El valor previo con la estadística individual no aporta** (0,0550 con y sin él): el rating de plus-minus ya recoge lo que dice la estadística, y la estadística no recoge más.
- En probabilidad de ganar la mejora sigue sin distinguirse del ruido (+0,0003, IC −0,0012 a +0,0018).
- **Tamaño**: un quinteto una desviación típica mejor que el rival vale ≈ 0,4-0,5 puntos cada 5 minutos (≈ 4 puntos en un partido): útil como criterio de rotación, pequeño como predictor.

## Experimento 4: otras familias de modelos (redes bayesianas, aprendizaje automático, redes neuronales)
Pregunta del usuario: ¿qué otros modelos predictivos encajan en el producto, con sus límites (motor en biblioteca estándar en la tablet con Pyodide, paquetes pequeños, 512 MB en Render, poco tiempo de cálculo)? Muestra: **2.886 partidos y 40.190 cortes**, ligas femeninas (las de arriba) y **masculinas** (Primera y Segunda FEB 2024-25 a 2026/27 de la base local).

### 4a. Comparación con validación cruzada por partido (5 grupos)

| Modelo | Log loss | Femeninas | Masculinas | Desvío máx. por decil | Diferencia con la app (IC 95 %) |
|---|---|---|---|---|---|
| A. Modelo de la app (parámetros actuales) | 0,4158 | 0,3938 | **0,4433** | **3,3 pp** | — |
| D. Logística: marcador, tiempo y valor previo | 0,4098 | 0,3917 | 0,4325 | 1,5 pp | −0,0060 (−0,0097 a −0,0019) |
| K. Logística + valor previo bayesiano dinámico (Kalman) | 0,4085 | 0,3912 | 0,4302 | 0,9 pp | −0,0073 (−0,0114 a −0,0029) |
| F2. Árboles potenciados (monótonos y regularizados), todo + Kalman | 0,4104 | 0,3921 | 0,4334 | 1,2 pp | −0,0054 (−0,0097 a −0,0006) |
| N. Red neuronal (32-16), todo + Kalman | 0,4176 | 0,3977 | 0,4426 | 3,9 pp | +0,0018 (−0,0029 a +0,0069) |

### 4b. El modelo de la app, calibrado por familia de competiciones
Con la mitad de los partidos se eligen `wp_sigma`, `wp_home_adv` y `wp_n0` para cada familia (femeninas, masculinas) y se puntúa la otra mitad (y al revés): tres números por familia, que caben en `rule_config`.

| Modelo | Log loss | Femeninas | Masculinas | Primeros 10 min | Desvío máx. por decil |
|---|---|---|---|---|---|
| A. App (parámetros actuales) | 0,4158 | 0,3938 | 0,4433 | 0,5281 | 3,3 pp |
| A3. Estructural calibrado por familia | 0,4105 | 0,3924 | 0,4332 | 0,5284 | 0,5 pp |
| A4. A3 + valor previo bayesiano (Kalman, cada temporada desde cero) | 0,4070 | 0,3892 | 0,4293 | 0,5227 | 0,7 pp |
| **A5. A3 + valor previo bayesiano con la temporada anterior** | **0,4063** | **0,3886** | **0,4286** | **0,5219** | 0,5 pp |

A3 − app: −0,0053 (IC 95 % −0,0076 a −0,0026) · A4 − app: **−0,0088** (−0,0120 a −0,0057) · A4 − A3: −0,0035 (−0,0057 a −0,0016) · A5 − app: −0,0095 (−0,0127 a −0,0065) · **A5 − A4: −0,0007 (−0,0015 a +0,0001)**. Parámetros elegidos: femeninas `wp_sigma` 12-14 y campo 4; masculinas **14-16 y campo 6**; en las dos `wp_n0` 960 (pesa más el valor previo que los cuatro factores del partido, coherente con los experimentos 1 y 2).

**Valor previo bayesiano dinámico (Kalman)**: el rating de cada equipo en puntos por partido se actualiza con cada resultado según lo seguro que se esté de cada equipo (su varianza), descuenta la fuerza del rival y la ventaja de campo, y deriva un poco durante la temporada. **FEB cambia el id de cada equipo cada temporada** (0 ids comunes entre temporadas; el `teamCode` de la cabecera sí se mantiene en 13 de 16-18 equipos): la versión A5 enlaza las temporadas por `teamCode` y arranca del rating anterior encogido al 60 %. **La temporada anterior aporta poco en esta medida** (−0,0007, sin llegar a ser distinguible del ruido) porque las muestras solo incluyen equipos con ≥ 3 partidos previos en la temporada: donde más ayudaría es en las tres primeras jornadas, que aquí no se miden. *(Una primera versión de este informe atribuía la mejora de A4 a la temporada anterior: no enlazaba equipos por el cambio de id; corregido.)* Es estadística bayesiana de espacio de estados, cuesta milisegundos en Python puro y solo necesita los **marcadores finales** de las temporadas anteriores (no las jugadas): se puede guardar como **un dato por equipo** al terminar cada temporada, sin partidos antiguos en la nube.

### Lectura por familia
| Familia | Resultado | Encaje en el producto |
|---|---|---|
| **Modelo estructural actual, recalibrado por familia** | −0,0053; arregla la descalibración de las ligas masculinas (de 3,3 a 0,5 pp) | Ideal: tres parámetros por competición en `rule_config`, nada cambia en la app; las palancas siguen saliendo del modelo |
| **Valor previo bayesiano dinámico (Kalman)** | −0,0035 más (A4); el mejor en los primeros 10 min; la temporada anterior añade −0,0007 (A5) | Ideal: lo calcula el publicador en Python puro y viaja como `net_rtg_prior`; la temporada anterior, si se usa, se guarda agregada (un dato por equipo) |
| Regresión logística | −0,0060 / −0,0073 con Kalman: buena, pero no mejor que A4 | Fácil (coeficientes en el paquete), pero pierde la estructura de la que salen las palancas |
| Árboles potenciados | −0,0054: no mejor que la logística | Posible (50-150 KB de árboles, evaluación de ms en Python puro), opaco, necesita restricciones monótonas; no compensa |
| Red neuronal | +0,0018: peor y peor calibrada | Exportable (≈ 1.600 pesos) pero opaca y sin ganancia con estos datos |
| **Redes bayesianas** (grafo de variables discretas) | No probadas | Mal encaje: las variables son continuas y van en el tiempo; discretizarlas pierde información y el modelo actual ya es una actualización bayesiana (valor previo + evidencia del partido, ponderadas por posesiones). La parte útil de lo bayesiano es el **valor previo dinámico** (4b) y la **agrupación por competición** (4b) |
| Modelos de secuencia (LSTM, transformers sobre jugada a jugada) | No probados | Necesitan decenas de miles de partidos (hay ≈ 3.000) y no corren en el motor de biblioteca estándar; descartados por ahora |

**Conclusión**: el límite no es el tipo de modelo sino **la información y la calibración**. Ninguna familia más compleja supera al modelo actual bien calibrado con un buen valor previo, y las dos mejoras con mejor encaje (**recalibrar por familia** y **valor previo bayesiano dinámico**) bajan el log loss en 0,0088 (≈ 2 %), más que todo lo probado antes, sin tocar la app ni el tamaño de los paquetes.

## Qué recomiendo (decisiones para el usuario)
1. **No sustituir el modelo, recalibrarlo**: ninguna familia más rica (logística, árboles, red neuronal) lo mejora con estos datos (experimento 4). Sí hay que **calibrarlo por familia de competiciones** (`wp_sigma`, `wp_home_adv`, `wp_n0` en `rule_config`): en las masculinas está descalibrado hoy (3,3 pp de desvío).
1b. **Valor previo bayesiano dinámico (Kalman) en el publicador**: es la mejora más grande y no cambia la app. Arrancar de la temporada anterior (un dato por equipo, enlazado por `teamCode`) se deja como mejora opcional para las primeras jornadas, cuando se mida con muestras desde la jornada 1.
2. **Quitar de los avisos las cifras causales** («+N % de victoria si vuelve a su nivel habitual» de `win_flip`, «+N % de victoria» de `pace_control`): no están respaldadas (experimento 2). Dejar la palanca como **diagnóstico** («el rival acierta el 75 % y nosotros el 60 %: nos cuesta unos 12 puntos cada 100 posesiones»), que sí es cierto de lo ocurrido.
3. **Partir las palancas en ataque y defensa** (lo que se pedía: «¿atacan bien?, ¿hay que mejorar la defensa?») **sin pretender predecir**: ataque = nuestro nivel frente a lo habitual de la liga, defensa = el del rival frente a lo habitual contra equipos como el nuestro. Requiere que el paquete lleve los cuatro factores de ataque y de defensa de la temporada de cada equipo (hoy solo lleva el prior de la *diferencia*): cambio de esquema del paquete (`schema_version`) y regenerar los publicados.
4. ~~Valor previo ajustado por rival (ridge)~~: lo supera el valor previo bayesiano dinámico (1b).
5. **Llevar el rating de jugador al paquete y a las alertas** (es lo único con señal): el publicador calcula, **en local** (la base compartida no guarda temporadas antiguas), el rating de cada jugadora con **varias temporadas** (RAPM con ridge ajustado por competición, ≈ 10 min de cálculo por competición) y solo se **publica el agregado** (unas decenas de bytes por jugadora, solo las de los equipos publicados) y lo guarda en `players` (`rating`); el motor lo usa para (a) una palanca individual («el quinteto en pista rinde X por 40 min menos que el mejor disponible», que alimenta la rotación), (b) un pequeño ajuste de la probabilidad de victoria y (c) la propuesta de cambios. Medir antes con un test A/B sobre grabaciones reales. Cambia el esquema del paquete (`schema_version`).
6. **Después, probar la calidad de tiro por zona** (`ShotChart`: tiros abiertos frente a forzados, que persisten más que el porcentaje) y el tipo de posesión: no probados aún.

## Límites
- Los experimentos 1 y 2 son **estadística de equipo agregada**; el 3 usa ratings muy ruidosos de una o dos temporadas; la calidad de tiro por zona y el tipo de posesión no se han probado.
- Solo ligas femeninas de FEB con jugada a jugada y los partidos de 2026/27 disponibles; no se han probado FBCYL ni las ligas masculinas más allá de 2026/27.
- Los entrenadores **reaccionan** a lo que ven (tiempos muertos, cambios): una palanca que persistiría sin hacer nada puede desaparecer porque se corrige; el estudio mide el efecto neto, no el de actuar.
- Los cortes son cada 5 min y los dos lados de un partido son espejos: se agrupa por partido en la validación, pero las muestras efectivas son 1.610 partidos, no 22.351.

## Reproducir
`python scripts/wp_model_study.py collect --out samples.pkl <carpetas con los partidos de UNA temporada de UNA competición cada una>` (≈ 18 min para las 8 carpetas; usa `data/historical_games/*` y los partidos de 2026/27 exportados de Mongo), después `python scripts/wp_model_study.py fit samples.pkl` (experimento 1), `benchmark samples.pkl [más.pkl]` (4a) y `structural samples.pkl [más.pkl]` (4b) y `python scripts/wp_model_study.py persistence samples.pkl` (experimento 2). `collect-lineups --out lineups.pkl <las mismas carpetas>` (≈ 8 min, 4 procesos) y `individual samples.pkl lineups.pkl` (experimento 3), y `persistence` incluye el 2b. Necesita scikit-learn y scipy.
