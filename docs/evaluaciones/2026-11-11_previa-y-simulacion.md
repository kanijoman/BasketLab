# Evaluación de la previa del partido y de la simulación de la liga (11/11/2026)

Cierra la épica #841 (PR 2, #851) y la decisión sobre el objetivo de ritmo (#857). Mide, **sin fugas** (cada pronóstico usa solo los partidos anteriores al que se juzga; lo comprueba `frontend/src/forecast/study/walkForward.test.ts`), lo que habrían dicho la «Previa del partido» y la «Simulación de la liga» sobre **12 temporadas completas, 2.561 partidos**:

- **Masculinas** (la base local): Primera FEB 2025-26 (271 partidos, 17 equipos), Segunda FEB Este (181) y Oeste (182) 2025-26: 634 partidos.
- **Femeninas** (`data/historical_games`, fase regular: sin eliminatorias y con cada grupo por separado): LF Endesa 2024-25 y 2025-26 (240), LF Challenge 2023-24, 2024-25 y 2025-26 (240), y L.F.-2 grupos A y B de 2024-25 y 2025-26 (181-182): 1.927 partidos.

Se reproduce con `python run_local_export.py --collection …` (las masculinas) y `cd frontend && npm run study:forecast` (≈ 4 s; informe en `frontend/test-results/forecast-study.md`). Las femeninas históricas no están en la base: se cargaron en una base en memoria con los mismos exportadores de filas (`export_collection`) y se leyeron igual. El motor es el de la web (`frontend/src/forecast/`), no una reimplementación. FBCYL no está evaluado (no hay una temporada completa con jugada a jugada).

## Resumen
1. **El pronóstico funciona y es honesto donde no.** Con 10 o más partidos previos del equipo menos conocido: acierto 73,2 %, log loss **0,535** frente a 0,681 de «el local gana lo que lleva ganando» (1.639 partidos). En **masculino** con 3-5 partidos previos no mejora a esa base (0,728 frente a 0,694); en **femenino** sí (0,643 frente a 0,702). Por debajo de 5 partidos sigue siendo lo menos fiable, de ahí la «confianza baja».
2. **Los escenarios cuadran con lo que pasó**: la bolsa se ancla siempre (0 fallos en 524 previas; el margen esperado se mueve 0,18 puntos de media) y los cuatro tramos de margen puntúan mejor que el reparto histórico (Brier 0,660 frente a 0,753; log score 1,196 frente a 1,392).
3. **Los objetivos de ataque y de defensa están calibrados en las dos familias.** Cuando el partido alcanza el objetivo, la probabilidad prevista (62 %) coincide con la frecuencia real (62 %), y mejora al pronóstico en esos partidos (Brier 0,163-0,175 frente a 0,180-0,187).
4. **El objetivo de ritmo no tiene respaldo, y las dos familias se contradicen** (detalle abajo): en masculino la realidad queda por debajo de lo previsto (44 % frente a 52 %) y en femenino por encima (63 % frente a 54 %). Decisión (#857, criterio del usuario: «si no hay respaldo, informativo»): **el ritmo deja de ser un objetivo con probabilidad y la página lo muestra como información** —el ritmo esperado y cómo fue la temporada a ritmo lento y alto—.
5. **La simulación de la liga mejora a «el orden de hoy se mantiene»** en el RPS de la posición final en **34 de los 36 cortes** (25/50/75 % de cada una de las 12 ligas): media 0,059 frente a 0,097 en femenino y 0,081 frente a 0,122 en masculino. En «ser primero» y «top 4» la base gana cuando el líder (o el top 4) de ese día no cambia; no es una ventaja sistemática en esas dos preguntas. 10.000 temporadas tardan ≈ 0,1-0,3 s en un PC.

## Pronóstico del partido
La probabilidad de victoria del equipo local con solo lo jugado antes de cada partido (rating bayesiano, ventaja de campo de la familia —masculina σ 15 y campo 7, femenina σ 14 y campo 5— y ritmo del emparejamiento), frente a «el local gana tantas veces como lleva ganando».

Por partidos previos del equipo menos conocido (las 12 ligas):

| Previos | Partidos | Acierto | Log loss | Log loss «gana el local» | Brier | Brier «gana el local» |
| --- | --- | --- | --- | --- | --- | --- |
| 0-2 | 275 | 59,3 % | 0,655 | 0,742 | 0,232 | 0,272 |
| 3-5 | 281 | 64,1 % | 0,664 | 0,700 | 0,233 | 0,253 |
| 6-9 | 366 | 68,9 % | 0,557 | 0,688 | 0,190 | 0,248 |
| 10+ | 1.639 | 73,2 % | 0,535 | 0,681 | 0,180 | 0,244 |

Por familia:

| Familia | Previos | Partidos | Acierto | Log loss | Log loss «gana el local» |
| --- | --- | --- | --- | --- | --- |
| Masculina | 0-2 | 69 | 56,5 % | 0,689 | 0,746 |
| Masculina | 3-5 | 69 | 55,1 % | 0,728 | 0,694 |
| Masculina | 6-9 | 92 | 62,0 % | 0,584 | 0,689 |
| Masculina | 10+ | 404 | 73,5 % | 0,547 | 0,677 |
| Femenina | 0-2 | 206 | 60,2 % | 0,643 | 0,740 |
| Femenina | 3-5 | 212 | 67,0 % | 0,643 | 0,702 |
| Femenina | 6-9 | 274 | 71,2 % | 0,548 | 0,688 |
| Femenina | 10+ | 1.235 | 73,1 % | 0,531 | 0,683 |
| Masculina | todos | 634 | 68,0 % | 0,587 | 0,688 |
| Femenina | todos | 1.927 | 70,8 % | 0,558 | 0,692 |
| **Todas** | todos | 2.561 | 70,1 % | 0,565 | 0,691 |

Es el mismo modelo que valida el motor en directo (#567, #825): lo difícil son las primeras jornadas; arrancar la temporada con el rating de la anterior (#825, aplazado) las mejoraría.

## Escenarios
524 previas (cada 4 partidos desde el 40.º de cada liga, desde el lado del local). La dispersión de los escenarios es de 11,7 puntos de media —por debajo de σ (14-15) porque los residuos son de la propia temporada— y el núcleo normal `σ_u` pone los 8,1 puntos que faltan: sin él los escenarios serían demasiado estrechos.

| | Previas | Fallos de anclaje | Dispersión (pts) | Núcleo σ_u (pts) | \|μ* − μ\| medio (pts) | Brier (4 clases) | Brier reparto histórico | Log score | Log score reparto histórico |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Masculina | 130 | 0 | 12,16 | 8,73 | 0,23 | 0,704 | 0,752 | 1,261 | 1,390 |
| Femenina | 394 | 0 | 11,51 | 7,82 | 0,16 | 0,645 | 0,753 | 1,175 | 1,393 |
| **Todas** | 524 | 0 | 11,67 | 8,05 | 0,18 | 0,660 | 0,753 | 1,196 | 1,392 |

## Objetivos del partido
Se comprueba cada objetivo (hasta tres de ataque y tres de defensa; y el ritmo, que se sigue midiendo aunque ya no se muestre) desde el lado de los dos equipos: ¿lo alcanzó el partido que se jugó?, ¿ganó el equipo del objetivo? Lo que se evalúa es la **probabilidad condicional** («en esos partidos ganamos el 46 %»), no que forzar el objetivo durante el partido cambie el resultado.

| Familia | Lado | Objetivos | Alcanzados | Prevista si se alcanza | Real si se alcanza | Real si no | Brier de la prevista | Brier del pronóstico |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Masculina | Ataque | 762 | 26 % | 63,8 % | 64,1 % | 45,9 % | 0,165 | 0,175 |
| Masculina | Defensa | 731 | 27 % | 60,9 % | 63,8 % | 44,1 % | 0,161 | 0,187 |
| Masculina | **Ritmo** | 111 | 23 % | 52,1 % | 44,0 % | 45,3 % | 0,135 | 0,132 |
| Femenina | Ataque | 2.235 | 27 % | 61,7 % | 61,2 % | 45,4 % | 0,178 | 0,191 |
| Femenina | Defensa | 2.258 | 25 % | 62,5 % | 61,6 % | 46,5 % | 0,164 | 0,178 |
| Femenina | **Ritmo** | 304 | 28 % | 54,1 % | 62,8 % | 44,0 % | 0,144 | 0,148 |
| Todas | Ataque | 2.997 | 27 % | 62,2 % | 61,9 % | 45,6 % | 0,175 | 0,187 |
| Todas | Defensa | 2.989 | 25 % | 62,1 % | 62,2 % | 46,0 % | 0,163 | 0,180 |
| Todas | **Ritmo** | 415 | 27 % | 53,6 % | 58,6 % | 44,4 % | 0,142 | 0,145 |

«Alcanzados» es el 26 % porque el umbral es el cuarto de los escenarios que mejor van (25 %): la masa es la prevista. Calibración de la probabilidad prevista cuando se alcanza el objetivo (todos los lados, las 12 ligas):

| Prevista | Objetivos | Prevista (media) | Real |
| --- | --- | --- | --- |
| 0 %–20 % | 109 | 13,3 % | 18,3 % |
| 20 %–40 % | 274 | 30,6 % | 25,2 % |
| 40 %–60 % | 355 | 50,2 % | 46,8 % |
| 60 %–80 % | 435 | 70,4 % | 73,8 % |
| 80 %–100 % | 503 | 89,4 % | 91,5 % |

Sin sesgo apreciable en el medio; en los extremos la realidad es algo más extrema que lo previsto (la previsión está un poco encogida hacia el centro).

### Ritmo (#857)
El ritmo no cumple lo que se le pedía a un objetivo, que es **ser mejor que el pronóstico y estar calibrado**:

- **No está calibrado ni siquiera en el signo**: en masculino la probabilidad prevista (52 %) queda **8 puntos por encima** de la real (44 %) y en femenino **9 puntos por debajo** (54 % frente a 63 %). Una previsión con un sesgo que cambia de signo según la familia no es una previsión en la que apoyarse.
- **No mejora al pronóstico**: Brier 0,135 frente a 0,132 (masculino, peor) y 0,144 frente a 0,148 (femenino, 0,004 mejor); todas: 0,142 frente a 0,145.
- **Son pocos casos**: con ≈ 28 % de objetivos alcanzados, femenino tiene ≈ 85 partidos con ritmo alcanzado (error típico de la frecuencia real ≈ 5 puntos) y masculino ≈ 26: las diferencias de 8-9 puntos son del orden del ruido. No hay evidencia ni a favor ni en contra, y sin evidencia no se muestra una cifra.

**Decisión**: la página muestra el ritmo como **información** (tarjeta «Ritmo (informativo)»): el ritmo esperado del emparejamiento (la media de lo que juegan los dos equipos) y cómo fue la temporada del equipo propio a ritmo lento (el cuarto más lento de los escenarios de ese emparejamiento) y alto, con la aclaración de que no se ha podido comprobar que el ritmo cambie la probabilidad de ganar. Ataque y defensa siguen siendo objetivos. El estudio sigue midiendo el ritmo como objetivo para poder recuperarlo si con más temporadas apareciera respaldo.

## Simulación de la liga
2.000 temporadas tras el 25, el 50 y el 75 % de cada liga, con los partidos del resto de la temporada como calendario, frente a la clasificación final. Línea base: «el orden de la tabla ese día se mantiene». Medias de los cortes de cada familia:

| Familia | Cortes | RPS | RPS orden actual | Brier 1.º | Brier 1.º orden actual | Brier top 4 | Brier top 4 orden actual | Mejor RPS que el orden actual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Masculina | 9 | 0,081 | 0,122 | 0,055 | 0,071 | 0,088 | 0,137 | 9 de 9 |
| Femenina | 27 | 0,059 | 0,097 | 0,029 | 0,039 | 0,062 | 0,109 | 25 de 27 |

Masculinas, por liga:

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

El RPS de la distribución completa es el que mejor describe la tabla y mejora en 34 de los 36 cortes. En «ser primero» y «top 4» la base gana cuando el líder (o el top 4) de ese día no cambia —un Brier de 0 de una pregunta de sí o no con un solo hecho—, así que no es una ventaja sistemática de la simulación en esas dos preguntas. Tiempo: 22-70 ms por 2.000 temporadas.

## Límites
- **FBCYL no está evaluado** y las femeninas solo son 2023-26: una temporada por liga y sin intervalos entre temporadas.
- Los niveles de cada equipo (lo que hace y deja hacer) se calculan con los partidos hasta ese día pero los escenarios usan esos niveles sobre los mismos partidos que los forman: los residuos son algo más estrechos que los reales; el núcleo `σ_u` lo compensa.
- Que un objetivo «se alcance» depende del propio partido: la probabilidad condicional describe lo que pasa en esos partidos; el estudio de octubre (#567) no encontró evidencia de que corregir un factor durante el partido cambie lo que viene después.
- El calendario de la simulación son los partidos que de hecho se jugaron tras el corte: sin aplazamientos ni cambios de última hora; en las femeninas históricas se usan solo los de la fase regular de cada grupo.
- No se modelan ascensos, descensos ni playoffs, ni el desempate recursivo de la federación.
