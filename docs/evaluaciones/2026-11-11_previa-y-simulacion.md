# Evaluación de la previa del partido y de la simulación de la liga (11/11/2026)

Cierra la épica #841 (PR 2, #851). Mide, **sin fugas** (cada pronóstico usa solo los partidos anteriores al que se juzga; lo comprueba `frontend/src/forecast/study/walkForward.test.ts`), lo que habrían dicho la «Previa del partido» y la «Simulación de la liga» sobre **tres temporadas masculinas completas** de la base local: Primera FEB 2025-26 (271 partidos), Segunda FEB Este (181) y Oeste (182) 2025-26: 634 partidos, 17 y 14 equipos. Las ligas femeninas y FBCYL no están: la base local solo tiene de ellas el arranque de 2026-27 (el estudio de octubre, #567, sí cubría las femeninas).

Se reproduce con `python run_local_export.py --collection …` y `cd frontend && npm run study:forecast` (≈ 4 s; informe en `frontend/test-results/forecast-study.md`). El motor es el de la web (`frontend/src/forecast/`), no una reimplementación.

## Resumen
1. **El pronóstico funciona donde ya se sabía que funciona y es honesto donde no.** Con 10 o más partidos previos del equipo menos conocido: acierto 73,5 %, log loss **0,547** frente a 0,677 de «el local gana lo que lleva ganando» (404 partidos). Con 3-5 partidos previos **no mejora** a esa base (0,728 frente a 0,694) y con 0-2 apenas (0,689 frente a 0,746): por eso la página marca **«confianza baja»** por debajo de 5 partidos.
2. **Los escenarios cuadran con lo que pasó**: la bolsa se ancla siempre (0 fallos en 130 previas, el margen esperado se mueve 0,23 puntos de media para dar exactamente la probabilidad del pronóstico) y los cuatro tramos de margen puntúan mejor que el reparto histórico de la competición (Brier 0,704 frente a 0,752; log score 1,261 frente a 1,390).
3. **Los objetivos de ataque y de defensa están calibrados; el de ritmo no tiene señal.** Cuando el partido alcanza el objetivo, la probabilidad prevista (61,7 %) coincide con la frecuencia real (62,8 %; ataque 63,8 % frente a 64,1 %; defensa 60,9 % frente a 63,8 %), y mejora al pronóstico en esos partidos (Brier 0,162 frente a 0,178). **El objetivo de ritmo** (111 casos) prevé 52 % y la realidad es 44 %, y su Brier (0,135) no mejora al del pronóstico (0,132): no hay evidencia de que sirva (issue #857).
4. **La simulación de la liga mejora a «el orden de hoy se mantiene»** en el RPS de la posición final en los **9 cortes** de las 3 ligas (p. ej. Primera: 0,130 / 0,074 / 0,044 frente a 0,169 / 0,118 / 0,081 tras el 25 / 50 / 75 % de la temporada) y en el Brier de ser primero en la mayoría; con tres ligas y pocos candidatos, el «orden de hoy» acierta a veces el primero o el top 4 (cuando el líder no cambia, su Brier es 0): no es una ventaja sistemática de la simulación en esas dos preguntas. 10.000 temporadas tardan ≈ 0,1-0,3 s en un PC.

## Pronóstico del partido
La probabilidad de victoria del equipo local con solo lo jugado antes de cada partido (rating bayesiano, ventaja de campo de la familia —masculina: σ 15 y campo 7— y ritmo del emparejamiento), frente a «el local gana tantas veces como lleva ganando».

| Previos | Partidos | Acierto | Log loss | Log loss «gana el local» | Brier | Brier «gana el local» |
| --- | --- | --- | --- | --- | --- | --- |
| 0-2 | 69 | 56,5 % | 0,689 | 0,746 | 0,249 | 0,275 |
| 3-5 | 69 | 55,1 % | 0,728 | 0,694 | 0,263 | 0,251 |
| 6-9 | 92 | 62,0 % | 0,584 | 0,689 | 0,202 | 0,248 |
| 10+ | 404 | 73,5 % | 0,547 | 0,677 | 0,186 | 0,242 |

| Competición | Partidos | Acierto | Log loss | Log loss «gana el local» | Brier | Brier «gana el local» |
| --- | --- | --- | --- | --- | --- | --- |
| Primera FEB 2025-26 | 271 | 71,2 % | 0,543 | 0,680 | 0,185 | 0,244 |
| Segunda FEB Este 2025-26 | 181 | 65,2 % | 0,626 | 0,693 | 0,219 | 0,250 |
| Segunda FEB Oeste 2025-26 | 182 | 65,9 % | 0,615 | 0,694 | 0,215 | 0,250 |
| Todas | 634 | 68,0 % | 0,587 | 0,688 | 0,203 | 0,247 |

Es el mismo modelo que valida el motor en directo (#567, #825: arrancar la temporada del rating anterior mejoraría las primeras jornadas, aplazado en #825) y se ve igual: lo difícil son las primeras jornadas.

## Escenarios
130 previas (cada 4 partidos desde el 40.º de cada liga, desde el lado del local). La dispersión de los escenarios es de 12,2 puntos de media —por debajo de σ = 15 porque los residuos son de la propia temporada (los niveles de los equipos incluyen esos partidos)— y el núcleo normal `σ_u` pone los 8,7 puntos que faltan: sin él los escenarios serían demasiado estrechos.

| | Brier (4 clases) | Log score |
| --- | --- | --- |
| Previa | 0,704 | 1,261 |
| Reparto histórico de la competición | 0,752 | 1,390 |

## Objetivos del partido
Se comprueba cada objetivo (hasta tres de ataque, tres de defensa y el ritmo) desde el lado de los dos equipos: ¿lo alcanzó el partido que se jugó?, ¿ganó el equipo del objetivo? Lo que se evalúa es la **probabilidad condicional**; es lo que dice la página («en esos partidos ganamos el 46 %») y no que forzar el objetivo durante el partido cambie el resultado.

| | Objetivos | Alcanzados | P(victoria) prevista si se alcanza | Victorias reales si se alcanza | Victorias reales si no | Brier de la prevista | Brier del pronóstico |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Todos | 1.604 | 26 % | 61,7 % | 62,8 % | 45,1 % | 0,162 | 0,178 |
| Ataque | 762 | 26 % | 63,8 % | 64,1 % | 45,9 % | 0,165 | 0,175 |
| Defensa | 731 | 27 % | 60,9 % | 63,8 % | 44,1 % | 0,161 | 0,187 |
| Ritmo | 111 | 23 % | 52,1 % | 44,0 % | 45,3 % | 0,135 | 0,132 |

«Alcanzados» es el 26 % porque el umbral es el cuarto de los escenarios que mejor van (25 %): la masa es la prevista. Calibración de la probabilidad prevista cuando se alcanza el objetivo:

| Prevista | Objetivos | Prevista (media) | Real |
| --- | --- | --- | --- |
| 0 %–20 % | 22 | 14,9 % | 0,0 % |
| 20 %–40 % | 62 | 30,8 % | 25,8 % |
| 40 %–60 % | 99 | 50,0 % | 54,5 % |
| 60 %–80 % | 128 | 70,1 % | 71,1 % |
| 80 %–100 % | 108 | 89,9 % | 94,4 % |

La realidad es algo más extrema que lo previsto en los dos extremos (la previsión está un poco encogida hacia el centro), sin sesgo en el medio. **El ritmo no se sostiene**: con 111 casos no hay evidencia de que su probabilidad condicional sea mejor que el pronóstico. Se propone retirarlo de la página (#857) en lugar de mostrar un objetivo sin respaldo.

## Simulación de la liga
2.000 temporadas tras el 25, el 50 y el 75 % de cada liga, con los partidos del resto de la temporada como calendario, frente a la clasificación final. Línea base: «el orden de la tabla ese día se mantiene».

| Liga | Corte | RPS | RPS orden actual | Brier 1.º | Brier 1.º orden actual | Brier top 4 | Brier top 4 orden actual |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Primera | 25 % | 0,130 | 0,169 | 0,076 | 0,118 | 0,088 | 0,000 |
| Primera | 50 % | 0,074 | 0,118 | 0,080 | 0,118 | 0,031 | 0,118 |
| Primera | 75 % | 0,044 | 0,081 | 0,060 | 0,118 | 0,005 | 0,118 |
| Segunda Este | 25 % | 0,125 | 0,209 | 0,069 | 0,143 | 0,218 | 0,286 |
| Segunda Este | 50 % | 0,097 | 0,121 | 0,064 | 0,143 | 0,188 | 0,286 |
| Segunda Este | 75 % | 0,036 | 0,044 | 0,033 | 0,000 | 0,100 | 0,143 |
| Segunda Oeste | 25 % | 0,102 | 0,154 | 0,019 | 0,000 | 0,059 | 0,000 |
| Segunda Oeste | 50 % | 0,059 | 0,110 | 0,060 | 0,000 | 0,030 | 0,143 |
| Segunda Oeste | 75 % | 0,065 | 0,088 | 0,035 | 0,000 | 0,070 | 0,143 |

El RPS de la distribución completa es el que mejor describe la tabla y mejora en los 9 cortes. En «ser primero» y «top 4» la base gana cuando el líder (o el top 4) de ese día no cambia —un Brier de 0 de una pregunta de sí o no con un solo hecho—: tres ligas no bastan para decir más. Tiempo: 22-63 ms por 2.000 temporadas.

## Límites
- **Solo ligas masculinas completas** (las que hay en la base local); las femeninas y FBCYL quedan por evaluar con el archivo.
- Los niveles de cada equipo (lo que hace y deja hacer) se calculan con los partidos hasta ese día pero los escenarios usan esos niveles sobre los mismos partidos que los forman: los residuos son algo más estrechos que los reales; el núcleo `σ_u` lo compensa.
- Que un objetivo «se alcance» depende del propio partido: la probabilidad condicional describe lo que pasa en esos partidos; el estudio de octubre (#567) no encontró evidencia de que corregir un factor durante el partido cambie lo que viene después.
- El calendario de la simulación son los partidos que de hecho se jugaron tras el corte: sin aplazamientos ni cambios de última hora.
- No se modelan ascensos, descensos ni playoffs, ni el desempate recursivo de la federación.
- Una temporada por liga: sin intervalos de confianza entre temporadas.
