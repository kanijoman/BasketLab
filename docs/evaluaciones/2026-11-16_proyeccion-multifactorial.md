# Evaluación de la proyección multifactorial de la previa (16/11/2026)

Parte de la épica #935 (#938). Feedback del staff: en la «Previa del partido», elegir condiciones del partido (puntos, ritmo, pérdidas, eFG del rival…) y ver la probabilidad de victoria en esos partidos **y cómo se mueve el resto del juego**. El motor (`frontend/src/forecast/projection/`, #936 y #937) juega cada escenario de la bolsa como un partido entero —posesiones, cuatro factores y puntos de cada lado = posesiones × minutos × puntos por 100 posesiones—, anclado al pronóstico. Esta evaluación decide qué llega a la página, con la regla de #857: **sin respaldo, información sin cifra**.

**Datos**: las 14 temporadas completas publicadas en `web-data` (fase regular FEB 2024-25 y 2025-26: LF Endesa, LF Challenge, L.F.-2 A y B, Primera FEB, Segunda FEB Este y Oeste), **2.994 partidos**: 1.306 masculinos (6 ligas) y 1.688 femeninos (8). La jugada a jugada (`possession_csv`) solo está en las 7 de 2025-26 (las anteriores se archivan sin ella). Se reproduce con `python scripts/web_data_dump.py --out DIR` (las filas publicadas, abiertas con la clave abierta de la beta, sin base de datos), `cd frontend && FORECAST_STUDY_DIR=DIR npm run study:projection` (3,4 min) y `python scripts/pace_style_study.py DIR`. Cada proyección usa **solo los partidos anteriores** al que se juzga (lo comprueba `study/projection.test.ts`), desde el partido 40 de cada liga y cada 4: 1.226 proyecciones desde los dos lados. FBCYL no está evaluado (no hay una temporada completa con jugada a jugada).

## Resumen
1. **El ritmo mueve el juego como intuye el staff, y en todas las ligas igual.** Por cada 10 % más de posesiones que las habituales de esos dos equipos: **+1,6 a +2,0 puntos de pérdidas**, −2,3 a −2,9 de rebote ofensivo, +2,7 a +3,2 de tiros libres por tiro y −2,8 a −3,2 puntos por 100 posesiones; los puntos de cada equipo suben (≈ +4 por 10 % de ritmo). El signo es el mismo en las 14 temporadas.
2. **Pero el ritmo de un partido varía poco** (se aleja ≈ 5 % de lo habitual de sus dos equipos) y explica poco de los puntos (correlación 0,23-0,27 con los de un equipo, 0,32-0,35 con el total). Saber las posesiones de un partido **no mejora** la previsión de sus puntos ni de su acierto; saber los puntos de un lado sí dice mucho de su acierto (error de su eFG de 7,8 a 5,4 puntos, de sus puntos por 100 posesiones de 13,5 a 5,6) y casi nada del ritmo o de los puntos del rival. «Anotamos más de 70» es, sobre todo, un partido de acierto.
3. **Cómo responde cada equipo al ritmo es ruido.** La pendiente de cada equipo con sus partidos impares no se parece a la de sus pares (correlación media −0,17 a 0,25 según la variable y la familia) y la capa de cada equipo **nunca prevé mejor** que la de la liga, con ningún encogimiento. **NO-GO a la capa de equipo** en la página (el código queda para seguir midiéndola).
4. **Lo que sí es propio de cada equipo es su forma de atacar**: la duración de sus posesiones (correlación par/impar 0,78, 0,88 en la temporada) y la de las que empieza tras canasta (0,76-0,80, 0,86-0,89), y su porcentaje de posesiones rápidas (0,59-0,62). Lo que anotan sus posesiones rápidas, no (≈ 0).
5. **Diez de las trece variables tienen respaldo** como probabilidad con condiciones: calibradas en las dos familias y mejores que el pronóstico en los partidos en que pasa la condición. **Sin respaldo**: las posesiones (como el 11/11), nuestras pérdidas (calibradas, pero no mejores que el pronóstico) y los puntos por 100 posesiones del rival (en femenino, 48 % previsto frente a 57 % real). Las condiciones raras (5 % de los escenarios) y las de dos variables a la vez también están calibradas: **el mínimo del 5 % se confirma**.
6. **Base para el estudio causal (#942)**: las posesiones rápidas anotan más **tras robo** (1,31 puntos por posesión en masculino, 1,15 en femenino) y **menos tras canasta** (0,82 frente a 1,02-1,04; 0,62 frente a 0,88-0,89), que es cuando el ritmo lo elige el equipo. Que «las rápidas anoten más» viene de las transiciones regaladas, no de jugar más rápido.
7. **Los objetivos del partido, calculados con la proyección, siguen calibrados** (sección e): la página da una sola cifra para cada condición, y «Cuidar el balón» pasa a información.
8. **Lo que hace el rival cuando la condición es nuestra** (sección f): la proyección lo lleva con la relación de la liga (0,13-0,16); la respuesta propia de cada rival es ruido (0,05-0,10), así que la tarjeta da su balance real en la misma situación como información.

## (a) Cómo se mueve el juego con el ritmo
La pendiente de la liga, temporada completa: lo que cambia cada cosa de un equipo por cada 10 % más de posesiones que las habituales de esos dos equipos (factores en puntos porcentuales; puntos por 100 posesiones en puntos).

| Familia | eFG | Pérdidas | Rebote ofensivo | Tiros libres por tiro | Puntos / 100 posesiones |
| --- | --- | --- | --- | --- | --- |
| Masculina (6 temporadas) | +0,37 | +1,60 | −2,92 | +3,20 | −3,21 |
| Femenina (8 temporadas) | +0,37 | +2,04 | −2,29 | +2,70 | −2,76 |

Pérdidas, rebote ofensivo, tiros libres y puntos por posesión tienen el mismo signo en las 14 temporadas; el eFG cambia de signo entre ligas (de −0,6 a +1,3) y no se mueve de forma clara. Parte de la relación es de definición: una pérdida termina una posesión y un rebote ofensivo la alarga, así que los partidos con más pérdidas y menos rebote ofensivo tienen más posesiones. Es lo que la lectura condicional describe («en los partidos rápidos hay más pérdidas»), no que jugar más rápido las cause.

Variación del ritmo y su relación con los puntos (todos los lados de todos los partidos):

| Familia | Lados | Desviación del ritmo frente a lo habitual | Correlación con los puntos del equipo | Con los puntos totales | Desviación de los puntos de un equipo |
| --- | --- | --- | --- | --- | --- |
| Masculina | 2.612 | 5,0 % | 0,27 | 0,35 | 11,7 |
| Femenina | 3.376 | 5,1 % | 0,23 | 0,32 | 12,5 |

## (b) Si es propio de cada equipo
**Por partidos** (la pendiente de cada equipo frente al ritmo, con sus partidos impares y con sus pares; lo que hace / lo que deja hacer; media de las temporadas):

| Familia | eFG | Pérdidas | Rebote ofensivo | Tiros libres por tiro | Puntos / 100 posesiones |
| --- | --- | --- | --- | --- | --- |
| Masculina | 0,24 / −0,07 | 0,05 / −0,13 | 0,09 / 0,01 | −0,12 / −0,08 | 0,25 / 0,04 |
| Femenina | 0,09 / −0,04 | 0,21 / 0,12 | −0,04 / 0,02 | 0,02 / −0,09 | 0,09 / −0,17 |

Ninguna se acerca a lo que haría falta para que la pendiente de un equipo sea suya (y las de cada temporada saltan de −0,6 a +0,7). Con una temporada por equipo, la pendiente de cada uno es ruido y la de la liga es lo que vale. Lo confirma la previsión (c): la capa de equipo con k = 5 partidos de encogimiento es la peor en todas las variables, con k = 20 algo mejor y con k = 80 casi igual que la de liga, nunca mejor; y su calibración es la misma que la de la capa de liga.

**Por posesiones** (`scripts/pace_style_study.py`, 7 temporadas de 2025-26; correlación par/impar y, entre paréntesis, la de la temporada entera por Spearman-Brown):

| Familia | Duración media | % de rápidas (≤ 8 s) | Puntos por posesión rápida | Puntos por posesión no rápida | Duración tras canasta | Duración de las del rival |
| --- | --- | --- | --- | --- | --- | --- |
| Masculina | 0,78 (0,88) | 0,59 (0,75) | −0,04 | 0,49 (0,66) | 0,80 (0,89) | 0,47 (0,64) |
| Femenina | 0,78 (0,87) | 0,62 (0,76) | 0,28 (0,44) | 0,65 (0,79) | 0,76 (0,86) | 0,31 (0,48) |

La forma de atacar —cuánto duran las posesiones, sobre todo tras canasta, y cuántas son rápidas— es un rasgo estable de cada equipo; lo que rinden sus rápidas no lo es. Cuánto hace durar un equipo las posesiones del rival lo es a medias.

## (c) Si la proyección predice
### Probabilidad con condiciones
Cada variable se pregunta una vez por partido y lado (dirección y umbral en el 5, 10, 25 o 50 % de los escenarios sorteados con una semilla del partido) y tres parejas por partido y lado; ¿lo cumplió el partido que se jugó?, ¿ganó el equipo? Capa de liga:

| Variable | Familia | Se cumplen | Prevista si se cumple | Real si se cumple | ± 2 errores típicos | Brier prevista | Brier pronóstico | Respaldo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Posesiones | M | 117 | 48,1 % | 50,4 % | ±9,2 | 0,198 | 0,199 | **no** |
| | F | 152 | 48,2 % | 44,1 % | ±8,1 | 0,165 | 0,162 | |
| Nuestros puntos | M | 123 | 47,0 % | 48,0 % | ±9,0 | 0,144 | 0,206 | sí |
| | F | 163 | 47,8 % | 45,4 % | ±7,8 | 0,135 | 0,184 | |
| Nuestros puntos / 100 pos. | M | 128 | 53,9 % | 54,7 % | ±8,8 | 0,180 | 0,214 | sí |
| | F | 159 | 52,0 % | 47,2 % | ±7,9 | 0,123 | 0,169 | |
| Nuestro eFG | M | 155 | 49,1 % | 45,8 % | ±8,0 | 0,146 | 0,194 | sí |
| | F | 193 | 48,8 % | 44,6 % | ±7,2 | 0,131 | 0,163 | |
| Nuestras pérdidas | M | 131 | 48,1 % | 45,8 % | ±8,7 | 0,198 | 0,198 | **no** |
| | F | 196 | 46,3 % | 43,4 % | ±7,1 | 0,180 | 0,179 | |
| Nuestro rebote ofensivo | M | 117 | 52,1 % | 57,3 % | ±9,1 | 0,196 | 0,208 | sí |
| | F | 138 | 53,0 % | 52,2 % | ±8,5 | 0,167 | 0,170 | |
| Nuestros tiros libres por tiro | M | 129 | 50,0 % | 51,9 % | ±8,8 | 0,174 | 0,175 | sí |
| | F | 144 | 47,8 % | 44,4 % | ±8,3 | 0,172 | 0,175 | |
| Sus puntos | M | 140 | 51,5 % | 50,7 % | ±8,5 | 0,158 | 0,203 | sí |
| | F | 166 | 42,9 % | 45,2 % | ±7,7 | 0,108 | 0,183 | |
| Sus puntos / 100 pos. | M | 125 | 45,7 % | 42,4 % | ±8,8 | 0,155 | 0,228 | **no** |
| | F | 171 | 47,5 % | **57,3 %** | ±7,6 | 0,156 | 0,184 | |
| Su eFG | M | 121 | 52,7 % | 55,4 % | ±9,0 | 0,159 | 0,187 | sí |
| | F | 139 | 46,8 % | 43,2 % | ±8,4 | 0,126 | 0,169 | |
| Sus pérdidas | M | 131 | 48,4 % | 46,6 % | ±8,7 | 0,197 | 0,206 | sí |
| | F | 174 | 52,1 % | 54,6 % | ±7,5 | 0,166 | 0,170 | |
| Su rebote ofensivo | M | 128 | 48,2 % | 44,5 % | ±8,8 | 0,194 | 0,196 | sí |
| | F | 129 | 46,3 % | 49,6 % | ±8,8 | 0,160 | 0,164 | |
| Sus tiros libres por tiro | M | 118 | 49,1 % | 45,8 % | ±9,2 | 0,190 | 0,194 | sí |
| | F | 181 | 48,7 % | 44,2 % | ±7,4 | 0,159 | 0,163 | |

Respaldo = en cada familia con 30 o más casos, la prevista a dos errores típicos de la real y un Brier no peor que el del pronóstico (el criterio con el que el 11/11 se juzgaron los objetivos). La capa de equipo da el mismo veredicto en las trece.

Por parte de los escenarios (capa de liga, todas las variables) y de dos en dos:

| | Masa prevista | Se cumplen | Prevista si se cumple | Real si se cumple | ± 2 errores típicos | Brier prevista | Brier pronóstico |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Umbral en el 5 % | 6,1 % | 300 | 49,4 % | 47,3 % | ±5,8 | 0,153 | 0,194 |
| Umbral en el 10 % | 11,2 % | 424 | 45,3 % | 44,1 % | ±4,8 | 0,135 | 0,198 |
| Umbral en el 25 % | 25,7 % | 1.009 | 49,1 % | 47,0 % | ±3,1 | 0,160 | 0,191 |
| Umbral en el 50 % | 49,7 % | 2.035 | 49,4 % | 49,5 % | ±2,2 | 0,169 | 0,178 |
| Dos condiciones, masculina | — | 402 | 48,3 % | 45,3 % | ±5,0 | 0,187 | 0,198 |
| Dos condiciones, femenina | — | 528 | 49,5 % | 49,1 % | ±4,4 | 0,142 | 0,169 |

### Prever el resto del partido
Sabiendo una variable del partido que se jugó (sus posesiones ±1, o los puntos de un lado ±2), el error cuadrático medio al prever las demás (factores en puntos porcentuales), sin condicionar y con la capa de liga; extracto:

| Sabiendo | Variable | Sin condicionar | Capa de liga |
| --- | --- | --- | --- |
| Posesiones | Nuestros puntos | 10,14 | 10,16 |
| Posesiones | Nuestras pérdidas | 4,22 | 4,14 |
| Posesiones | Nuestro eFG | 7,77 | 7,92 |
| Nuestros puntos | Nuestros puntos / 100 pos. | 13,47 | 5,61 |
| Nuestros puntos | Nuestro eFG | 7,77 | 5,37 |
| Nuestros puntos | Posesiones | 3,82 | 3,74 |
| Nuestros puntos | Sus puntos | 10,14 | 9,98 |

## (d) Duración y origen de las posesiones (base para #942)
Puntos por posesión según cómo empezó y cuánto duró (2025-26, sin las posesiones dudosas del CSV):

| Origen | Familia | Rápida (≤ 8 s) | Media (8-16 s) | Lenta (> 16 s) | % de rápidas |
| --- | --- | --- | --- | --- | --- |
| Tras robo | M | **1,306** | 1,127 | 1,078 | 53,7 % |
| | F | **1,153** | 0,981 | 0,950 | 47,6 % |
| Tras rebote defensivo | M | 1,043 | 1,087 | 1,075 | 22,9 % |
| | F | 0,842 | 0,941 | 0,914 | 19,4 % |
| Tras canasta o tiros libres | M | **0,824** | 1,023 | 1,036 | 9,2 % |
| | F | **0,623** | 0,879 | 0,894 | 8,4 % |

Las rápidas tras robo son transiciones que el rival regala; las rápidas tras canasta (las que elige el equipo) rinden menos que las demás. Puede que parte de esas rápidas tras canasta sean tiros apurados al final de un cuarto o del partido (selección): es lo que tendrá que separar el estudio causal.

## (e) Los objetivos del partido con el motor de la proyección (#941)
Un objetivo es una condición en el cuarto de los escenarios que mejor va en un factor; ahora su probabilidad, la parte de los partidos y el balance de la temporada son la respuesta de la proyección a esa condición, la misma que da la tarjeta «¿Y si…?» (`levers.ts`), así que la página no da dos cifras distintas para lo mismo. La evaluación walk-forward de la previa (`cd frontend && FORECAST_STUDY_DIR=DIR npm run study:forecast`, las mismas 14 temporadas, 40 s), con el cálculo anterior (cada escenario con su margen) y con el de la proyección (los puntos de cada lado):

| Familia | Lado | Cálculo | Objetivos | Prevista si se alcanza | Real si se alcanza | Brier de la prevista | Brier del pronóstico |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Masculina | Ataque | anterior | 1.580 | 61,3 % | 63,7 % | 0,174 | 0,193 |
| | | proyección | 1.392 | 64,4 % | 66,2 % | 0,170 | 0,191 |
| Masculina | Defensa | anterior | 1.516 | 60,2 % | 61,6 % | 0,182 | 0,202 |
| | | proyección | 1.552 | 61,1 % | 62,8 % | 0,177 | 0,198 |
| Femenina | Ataque | anterior | 1.966 | 62,2 % | 61,7 % | 0,165 | 0,178 |
| | | proyección | 1.791 | 65,7 % | 65,9 % | 0,166 | 0,181 |
| Femenina | Defensa | anterior | 1.966 | 63,2 % | 62,0 % | 0,162 | 0,174 |
| | | proyección | 1.994 | 64,1 % | 62,5 % | 0,167 | 0,177 |

Los objetivos se alcanzan en el 25-28 % de los partidos, así que dos errores típicos son ±4,5-5 puntos: **con la proyección siguen calibrados** (a menos de dos puntos de lo real en las cuatro filas) y **mejoran al pronóstico** en los partidos en que se alcanzan, como con el cálculo anterior. Los de ataque son menos porque «Cuidar el balón» ya no es un objetivo (decisión 5); el ritmo, que la página da como información, sigue sin respaldo (masculina 49,9 % previsto frente a 46,2 % real; femenina 58,9 % frente a 59,3 %, con un Brier igual al del pronóstico). El resto del informe (pronóstico, escenarios, simulación de la liga) no cambia.

## (f) Lo que hace el rival cuando la condición es nuestra (#940)
Pregunta del usuario: con «anotamos más de 70», ¿se tiene en cuenta qué hace el rival cuando le anotan más de 70? **Sí, con la relación de la liga**: cada escenario es un partido real con los dos lados juntos, así que la condición sobre nuestros puntos trae lo que hizo el rival en esos mismos partidos (en León – Lima-Horta, los puntos de Lima-Horta pasan de 67 a 69), y el resultado sale de comparar los dos. Lo que no usa es la respuesta **propia de cada rival**. ¿Haría falta? `rivalResponse` (`study/projection.ts`, sección «Lo que hace el rival» del informe de `npm run study:projection`), media de las temporadas:

| Familia | Liga: eficiencia de los dos | Liga: puntos de los dos | Propio: eficiencia | Propio: puntos | Propio: victorias al encajar más |
| --- | --- | --- | --- | --- | --- |
| Masculina (6) | 0,16 | 0,15 | 0,07 | 0,09 | 0,07 |
| Femenina (8) | 0,13 | −0,01 | 0,05 | 0,10 | −0,09 |

Las dos primeras columnas son la correlación, sobre todos los lados de todos los partidos, de lo que el rival hizo sobre lo esperado (puntos por 100 posesiones) con lo que hicimos nosotros, y de los puntos de los dos: **la relación existe en la liga** (cuando un equipo es más eficiente de lo esperado, el otro también un poco) y la proyección ya la lleva. Las tres últimas son la fiabilidad par/impar, entre los equipos de una temporada, de la respuesta de cada uno (la pendiente de su eficiencia frente a la del rival, la de sus puntos frente a los que encaja y cuánto más gana cuando el rival hace más de lo esperado): **ruido** (de −0,54 a 0,54 según la temporada, media cercana a 0), como la respuesta al ritmo (b). Usar la de cada rival añadiría error. Por eso la tarjeta da, como información, **el balance real del rival en la misma situación** (sus partidos con las condiciones vistas desde su lado: «con su rival en nuestro lugar») junto al nuestro, sin hacerlo pasar por un modelo.

## Decisiones
1. **Respaldo por variable** (fijado en `projection/variables.ts`, `UNBACKED`): diez con cifra (nuestros puntos, nuestros puntos por 100 posesiones, nuestro eFG, rebote ofensivo y tiros libres; sus puntos, su eFG, sus pérdidas, su rebote ofensivo y sus tiros libres) y tres solo como información: **posesiones**, **nuestras pérdidas** y **sus puntos por 100 posesiones**. Una condición que combine una con respaldo y otra sin él no da cifra.
2. **Capa de equipo: NO-GO** para la página; la proyección usa la relación de la liga. `paceResponse.ts` se queda para que el estudio la siga midiendo (con más temporadas por equipo podría aparecer).
3. **Mínimo del 5 % y combinaciones de dos condiciones: confirmados** (calibrados).
4. **#939 (duración de las posesiones en las filas): aplazado** (decisión del usuario, 16/11/2026). La duración es un rasgo estable de cada equipo (0,78), pero es otra forma de medir el ritmo y el ritmo no tiene respaldo como probabilidad de ganar; publicarla cambiaría el contrato de las filas para una variable que solo sería información.
5. **#941: los objetivos se calculan con la proyección** (calibrados, sección e). **«Cuidar el balón» pasa a información** (decisión del usuario, 16/11/2026: la regla de #857 y lo que dice la tarjeta): las pérdidas propias están calibradas pero no mejoran al pronóstico, así que la página da lo esperado y cómo fue la temporada con pocas y con muchas pérdidas, sin probabilidad. La regla queda general: un factor sin respaldo en `variables.ts` es información y no objetivo.
6. **El rival, con la relación de la liga y su balance como información** (#940, sección f): no se modela la respuesta de cada rival; la tarjeta enseña su balance en la misma situación junto al nuestro.

## Prueba del 16/11/2026 con el motor
B.F. León – Lima-Horta (2524505, LF Challenge 2026-27, J7, en León): pronóstico 47,9 %. «León anota más de 70»: pasa en 37 de cada 100 partidos como este y en esos gana el **75 %** (el prototipo del mismo día daba un 80 % porque no contaba los minutos de las prórrogas, que suben los puntos de los dos). En esos partidos León anota 77 (habitual 67) y Lima-Horta 69 (67); los puntos de más salen del acierto (≈ +9: eFG 42,9 → 46,6 %) más que de las posesiones jugadas (≈ +1,4, prórrogas incluidas). Esta temporada León pasó de 70 en 3 partidos y ganó 2 (73-84, 82-81 y 78-71); Lima-Horta, en la misma situación (encajando más de 70), jugó 1 y lo perdió (64-73). Es lo que da la tarjeta de la página (#940).

## Límites
- **Una temporada por equipo**: con más temporadas la pendiente de cada equipo frente al ritmo podría dejar de ser ruido; la capa queda para medirlo.
- **FBCYL no está evaluado**, y la jugada a jugada solo es de 2025-26.
- **Condicional, no causal**: la probabilidad describe los partidos en que pasó la condición; no dice que forzarla haga ganar (los entrenadores reaccionan a lo que ven, estudio del 26/10/2026). El simulador causal es #942.
- **Los escenarios usan los niveles de la propia temporada** (residuos algo estrechos, que el núcleo compensa) y los umbrales del estudio salen de los escenarios, no de lo que pediría el staff: los de la página serán otros, pero la calibración no depende del umbral (se mantiene del 5 al 50 %).
- Parte de la relación entre el ritmo y las pérdidas o el rebote ofensivo es de definición de posesión, no de juego.
