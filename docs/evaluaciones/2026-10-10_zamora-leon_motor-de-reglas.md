# Evaluación del motor de reglas con un partido real — Zamora 59 – 38 León (LF Challenge, jornada 2)

**Qué es**: el motor live (`LiveSession`) se ha ejecutado sobre la grabación real del partido (código 2524470, 10/10/2026) como si fuese en directo: 353 actualizaciones del feed, con un paquete de preparación construido con **solo los 8 partidos jugados antes** (los mismos datos de los que habría dispuesto el staff). Después se ha comparado cada sugerencia con lo que ocurrió en pista.

**Cómo leerlo (límites)**
- Un único partido y un **resultado muy desfavorable** (León perdió de 21; −20 con 8 min por jugar). El banquillo pudo decidir sin urgencia y eso sesga la conducta. No son conclusiones, son hipótesis para validar.
- «Seguida» = el cambio propuesto ocurrió **después de que la alerta fuera visible** (se descuentan 40 s: mediana real del retraso del feed) y dentro de 5 min de juego. Lo ocurrido antes o a la vez se llama «anticipada»: el entrenador ya lo había decidido. No sabemos si el staff llegó a ver las alertas: esto mide coincidencia, no obediencia.
- Para los umbrales de «qué hacen los entrenadores» se han usado los **16 partidos** ya jugados de la competición (118 tiempos muertos, 925 relevos por decisión propia, 270 faltas de jugadores en apuros).
- Los tiempos se dan como FEB los muestra: cuarto y tiempo **restante** del cuarto.

## 1. Qué generó el motor: 28 alertas

| Regla | Alertas | Observación |
|---|---:|---|
| Fatiga alta (`fatigue_high`) | 6 | todas con propuesta de relevo |
| Palanca de Four Factors (`four_factors_lever`) | 5 | 4 de eFG%, 1 de rebote ofensivo; **repetidas** durante todo el partido |
| Rival con problemas de faltas / cerca del bonus | 4 + 2 | informativas |
| Faltas propias (`foul_trouble`) | 4 | 3 avisos + 1 crítica (4.ª falta) |
| Bonus propio (`team_fouls_bonus`) | 2 | |
| Racha de pérdidas (`turnover_streak`) | 2 | |
| Jugador rival «haciendo daño» / zona del rival | 2 + 1 | |
| **Parcial rival 0-8 (`run`)** | **0** | nunca saltó (ver R1) |

Unas 0,7 alertas por minuto de juego; 9 de 28 (32 %) llevaban una propuesta de cambio concreta.

## 2. ¿Se siguieron las sugerencias?

### 2.1 Las 9 propuestas de relevo («sale X, entra Y»)

| Alerta (cuarto · tiempo restante) | Resultado | Detalle |
|---|---|---|
| 1.º 6:56 · S. Castro, 2 faltas | **anticipada** | ya había salido en el mismo segundo de su 2.ª falta (entró Dembélé, justo el propuesto) |
| 1.º 0:00 · Dembélé, fatiga (stint 6:56) | **tarde** | salió 6:22 después (2.º 3:38, junto al tiempo muerto); entró otro jugador |
| 2.º 5:51 · Dembélé, fatiga (stint 10:05) | **seguida** | salió a los 2:13 y entró exactamente el propuesto (Castro) |
| 2.º 4:08 · A. Martín, fatiga | **tarde** | siguió 11:30 más; salió en el 3.er cuarto |
| 2.º 0:00 · A. Martín, fatiga 100/100 | **tarde** | alerta en el descanso largo; salió a los 7:22 del 3.º |
| 3.º 3:05 · A. Martín, fatiga | **anticipada** | salió a los 27 s (menos que el retraso del feed) |
| 4.º 7:46 · S. Castro, 3 faltas | **tarde** | salió 5:31 después, justo con su 4.ª falta; el relevo coincide con el propuesto |
| 4.º 5:59 · A. Martín, 3 faltas | **no seguida** | jugó hasta el final con 3 faltas (sin consecuencia) |
| 4.º 3:38 · Martínez Llamazares, fatiga | **no seguida** | continuó en pista (partido ya decidido) |

Resumen: **1 seguida con el jugador propuesto**, 2 anticipadas, 4 tardías, 2 no seguidas. El relevo concreto propuesto coincidió con el real en 3 de 9 (en los tres el entrenador ya iba a cambiar por otra razón).
Lo más claro: **A. Martín** recibió tres avisos de fatiga (stints de 6:47, 10:55 y 6:55) y no se le cambió hasta pasados más de 11 min de juego; **S. Castro** con 3 faltas en el 4.º cuarto no se retiró hasta la 4.ª. La 4.ª falta (crítica, 2:15 del 4.º) coincidió con su salida.

### 2.2 Alertas sin cambio asociado (efecto medido, no «seguimiento»)

| Regla | Medida | Resultado |
|---|---|---|
| `turnover_streak` (2) | tiempo muerto / pérdidas en los 5 min siguientes | la 1.ª llegó **42 s después** de un tiempo muerto ya pedido; la 2.ª, 140 s antes del tiempo muerto del 3.er cuarto (probablemente relacionado); pérdidas siguientes: 6 (antes 4) y 2 (antes 6) |
| `four_factors_lever` (5) | eFG% de León en los 5 min posteriores | 0,38 · 0,25 · 0,29 · 0,21 · (1 tiro): **no mejora** (media ≈ 0,28 frente a ≈ 0,29 antes); el partido acabó en eFG ≈ 29 % |
| `team_fouls_bonus` (2) | faltas propias más en el periodo | 1.º: 1 más (entró en bonus); 4.º: 0 |
| `rival_foul_trouble` / `rival_near_bonus` (6) | tiros libres propios en los 5 min siguientes | 0 · 2 · 2 · 0 · 0 · 2: **apenas se explotó** (6 TL en total) |
| `rival_hot_player` / `rival_zone` (3) | puntos del rival en los 5 min siguientes | 6 · 7 · 11 (antes 10 · 9 · 10): sin efecto apreciable |

## 3. Patrones y reglas candidatas

Cada propuesta indica evidencia (de este partido y de los 16 de la competición). Los umbrales son puntos de partida para confirmar con el staff.

**R1. Parcial rival más sensible y por niveles.** El motor solo avisa con 0-8 en 2:30; en toda la competición esa condición precede al **5 %** de los tiempos muertos (6 de 118) y salta 0,3 veces por equipo y partido (en este, nunca; sin embargo los 3 tiempos muertos de León llegaron con parciales de −4, −5 y −6 en 2:30). Simulación sobre los 16 partidos:

| Condición (diferencia neta del rival) | Avisos por equipo y partido | Seguidos de tiempo muerto ≤ 2 min | Tiempos muertos «cubiertos» |
|---|---:|---:|---:|
| 8 sin respuesta en 150 s (actual) | 0,3 | 60 % | 5 % |
| ≥ 8 neto en 150 s | 0,7 | 57 % | 10 % |
| ≥ 6 neto en 150 s | 2,1 | 37 % | 21 % |

→ Propuesta: **dos niveles** (info a +6 neto en 150 s, aviso a +8 neto), manteniendo el 0-8 actual como crítico.

**R2. Sequía anotadora propia.** León estuvo **6:19, 4:31 y 4:24 sin anotar** (desde el minuto 11:32, 17:51 y 28:41 de juego) y el motor no tiene regla de sequía; solo repitió el eFG%. El primer tiempo muerto llegó a los 4:50 de la primera sequía. → Sin anotar (campo o TL) ≥ 4:00 → sugerir tiempo muerto / cambio de sistema; rival ≥ 3:30 sin anotar → ventana para correr.

**R3. Pérdidas → tiempo muerto.** La racha de pérdidas ya existe pero no propone nada. 31 de 118 tiempos muertos (26 %) siguen a ≥ 4 pérdidas propias en 5 min, y León pidió el suyo del 3.er cuarto con 5. → Añadir la propuesta «tiempo muerto» al `turnover_streak` y no avisar si el equipo acaba de pedirlo.

**R4. Faltas: dónde aporta valor el motor.** Frecuencia con que el entrenador retira al jugador en los 2 min siguientes a una falta (16 partidos):

| Falta personal | 1.º-2.º cuarto | 3.º | 4.º |
|---|---:|---:|---:|
| 2.ª | 82 % | 47 % | 40 % |
| 3.ª | 89 % | 68 % | 42 % |
| 4.ª | — | 100 % | 68 % |

En la primera parte los entrenadores ya actúan solos (el aviso de 2 faltas en el 1.º cuarto es casi siempre redundante: aquí llegó con el cambio ya hecho). **El motor aporta más en el 3.º y 4.º cuarto**: 3 faltas en el 4.º se gestionan solo en el 42 % de los casos. → Priorizar los avisos de 3.º/4.º y calcular **riesgo de eliminación** = faltas × tiempo restante (p. ej. 3 faltas con > 6:00 por jugar) en lugar de un umbral fijo por periodo.

**R5. Fatiga: calibración razonable, repetición mejorable.** Los relevos por decisión del entrenador duran de mediana 5:00 (cuartiles 3:29–7:01; p90 9:23) y el 26 % pasan de 7:00. El motor avisó con stints de 6:47–10:55, es decir, en el cuartil alto de lo que hacen los entrenadores: coherente. Dos mejoras: (a) los componentes por minutos jugados solo se activan a los 10 min de partido (`fatigue_min_elapsed_s`), por lo que en el 1.º cuarto el primer aviso sale «al final» (aquí a 0:00); (b) **escalar** (info → aviso → crítica) en lugar de repetir el mismo aviso para el mismo jugador (A. Martín: 3 avisos iguales).

**R6. Alertas «de estado» repetidas.** 5 de las 28 alertas son la misma palanca (eFG%, con el equipo en ≈ 29 % todo el partido) cada 10 min sin cambio medible. → Emitir solo si cambia la palanca principal o empeora ≥ X puntos/100 posesiones, y resumir en un mensaje persistente. Reduce ruido (−18 % de alertas aquí).

**R7. Modo «partido decidido».** Con −20 a 8:00 del final el motor siguió enviando relevos por fatiga y palancas de Four Factors que nadie iba a usar (las 2 «no seguidas»). → Regla de contexto: con |diferencia| ≥ 20 y < 8 min (umbral a confirmar) bajar la severidad de las alertas de rendimiento y priorizar gestión de minutos/faltas.

**R8. Explotar las faltas del rival.** Hubo 6 alertas sobre el rival con 3-4 faltas o cerca del bonus y León tiró solo 6 tiros libres en los 5 min posteriores. → Añadir propuesta táctica concreta (balón a quien busca contacto, atacar al jugador con 3-4 faltas) y medir en directo los tiros libres obtenidos tras el aviso.

**R9 (a validar con más datos; cálculo aproximado). Quinteto en negativo.** El quinteto Castañeda–Castro–Llamazares–Manna–Menéndez jugó 4:38 con −7 (4-11), mientras otra combinación salió con +4 en 4:02. «Quinteto con diferencia ≤ −6 en ≥ 3 min» solo se puede calibrar con más partidos (la tabla de quintetos del paquete ya existe).

## 4. Sobre el propio análisis

- **Latencia**: mediana de 39 s del evento a su visibilidad, p95 59 s. Las alertas tácticas de ventana corta (parciales, pérdidas) llegan cuando el entrenador a menudo ya ha reaccionado (ocurrió con la 1.ª racha de pérdidas). El sondeo ya es de 10 s y FEB cachea 15 s: poco margen.
- **Datos previos escasos**: con 8 partidos las líneas base de jugador son ruidosas, así que las propuestas de «quién entra» son poco fiables todavía; su acierto no puede medirse con un solo partido.
- **Qué falta para evaluar de verdad**: grabar **más partidos de León** (el planner debe cubrir la ventana previa, #205) y registrar si el staff **vio/usó** las alertas (botón «seguida / descartada» en la app) para pasar de coincidencia a obediencia.

## 5. Siguientes pasos sugeridos
1. Confirmar con el staff las reglas R1-R4 y R7 (mayor valor / menor riesgo) y crear un issue por regla aceptada.
2. Convertir este análisis en una **herramienta repetible** (p. ej. `python -m src.live_prep.rule_evaluation <grabación>`) para ejecutarla tras cada partido grabado y acumular métricas de seguimiento.
3. Reevaluar umbrales cuando haya ≥ 5 partidos grabados de León.

*Método y datos*: paquete de 8 partidos previos de LF Challenge 2026/27 (scraper FEB), grabación `recording-2524470` (1825 peticiones, 353 actualizaciones), PBP final del partido y PBP de los 16 partidos disputados; scripts de análisis puntuales (no incluidos en el repositorio).
