# Reglas del motor live: evidencia, catálogo y estado
Documento vivo. **Decisión (2026-10-13, sustituye a la del 11/10 de esperar a 5 partidos de León)**: el motor evoluciona de forma continua, así que las reglas de este documento se integran **activas** con la épica #260 (Motor de alertas v2) y se miden después con el evaluador de reglas (#238) y el feedback del staff (#235); cada regla tiene un interruptor `rules_off` en el paquete (#236) por si resulta ruidosa. Sin objetivo de volumen: toda propuesta de acción detectada se emite y la verbosidad se evalúa con datos. Origen: [evaluación Zamora–León](evaluaciones/2026-10-10_zamora-leon_motor-de-reglas.md) (1 partido, resultado muy desfavorable), el comportamiento de los entrenadores en los 16 partidos de LF Challenge y el catálogo del 13/10 (abajo). Motor actual: [LIVE.md](LIVE.md); umbrales: `RuleConfig` en `src/live_core/config.py`, todos **provisionales** a confirmar con el staff. Seguimiento en GitHub: épica #260 y #207.

## Candidatas
Estado: **candidata** (sin integrar) · **integrada** (activa en el motor, pendiente de medir) · **validada** (cumple los criterios de abajo, pendiente de confirmar con el staff) · **descartada**. Los umbrales son puntos de partida.

| ID | Regla propuesta | Evidencia (1 partido + 16 de la competición) | Cómo validarla con más datos | Estado |
|---|---|---|---|---|
| R1 | **Parcial rival por niveles**: info a +6 neto en 150 s, aviso a +8 neto, crítica con el 0-8 actual | 0-8 actual precede al 5 % de los tiempos muertos (6/118) y no saltó nunca en el partido; +6 neto cubre el 21 % (2,1 avisos/equipo y partido, 37 % seguidos de tiempo muerto ≤ 2 min) | Repetir la simulación (script 3) con todos los partidos disponibles; buscar el umbral con mejor equilibrio avisos/aciertos | integrada (#241; falta medirla) |
| R2 | **Sequía anotadora propia** ≥ 4:00 sin anotar → sugerir tiempo muerto/cambio de sistema; rival ≥ 3:30 sin anotar → ventana para correr | León: sequías de 6:19, 4:31 y 4:24; el primer tiempo muerto llegó a los 4:50 de la primera | Medir en todos los partidos qué fracción de sequías ≥ 4:00 acaba en tiempo muerto y si cambia el siguiente parcial | candidata |
| R3 | **Pérdidas → tiempo muerto**: el aviso de racha de pérdidas propone tiempo muerto y se calla si acaba de pedirse | 31/118 tiempos muertos (26 %) siguen a ≥ 4 pérdidas propias en 5 min; la 1.ª alerta llegó 42 s después de un tiempo muerto | Contar cuántas rachas ya tenían tiempo muerto previo; efecto en pérdidas siguientes | integrada (#241; falta medirla) |
| R4 | **Faltas por riesgo de eliminación** = faltas × tiempo restante (p. ej. 3 faltas con > 6:00), priorizando 3.º/4.º cuarto; no avisar de 2 faltas en el 1.º-2.º cuarto | Retirada en ≤ 2 min: 2.ª falta 82 % (1.º-2.º) / 47 % (3.º) / 40 % (4.º); 3.ª falta 89 % / 68 % / 42 %; 4.ª 100 % / 68 % | Más partidos para ver si el patrón se mantiene y si hay eliminaciones evitables | integrada (#241; falta medirla) |
| R5 | **Fatiga escalada** (info → aviso → crítica) sin repetir el mismo aviso; primer aviso por stint antes de los 10 min | Relevos del entrenador: mediana 5:00, p75 7:01, p90 9:23; el motor avisó a 6:47-10:55; A. Martín recibió 3 avisos iguales y siguió 11 min más | Comparar stints reales con el índice de fatiga en todos los partidos (calibrar pesos) | integrada (#241; falta medirla) |
| R6 | **Sin alertas de estado repetidas**: la palanca de Four Factors solo si cambia de palanca o empeora ≥ X pts/100 | 5 de 28 alertas eran el mismo eFG% (≈ 29 %) sin efecto medible | Contar duplicados por partido; X a definir con el staff | integrada (#241; falta medirla) |
| R7 | **Modo «partido decidido»**: con \|diferencia\| ≥ 20 y < 8 min, bajar la severidad de alertas de rendimiento y priorizar minutos/faltas | −20 a 8:00; las 2 propuestas «no seguidas» fueron en ese tramo | Necesita partidos igualados y de resultado abierto para fijar el umbral | integrada (#239; falta medirla) |
| R8 | **Explotar faltas del rival**: propuesta táctica concreta y medición de tiros libres obtenidos tras el aviso | 6 avisos sobre el rival con 3-4 faltas; León tiró 6 TL en los 5 min siguientes | Tasa de TL tras aviso en más partidos | integrada (#241; falta medirla) |
| R9 | **Quinteto en negativo**: diferencia ≤ −6 en ≥ 3 min | Un quinteto jugó 4:38 con −7 (cálculo aproximado) | Necesita muchos partidos; usar la tabla de quintetos del paquete | candidata |

## Catálogo de reglas nuevas (épica #260)
Todas con acción propuesta y horizonte mayor que la latencia del feed (mediana 39 s). Los R1-R9 de arriba y el rediseño de las reglas actuales van en #241; las reglas nuevas, por bloque:

| Bloque (issue) | Reglas |
|---|---|
| Flujo del partido (#242, **hecho**) | R2 sequía propia ≥ 4:00 y rival ≥ 3:30 · P2 sequía de canasta en juego ≥ 3:00 · P3 parcial largo −10 neto en 5 min · P4 parcial propio +8 · G2 ≥ 3 rebotes ofensivos rivales en 3 min · G3 ≥ 6 puntos rivales tras pérdida en 3 min · G5 rival con ≥ 4 pérdidas en 3 min |
| Rachas de tiro (#243, **hecho**) | T1 racha fría propia (≤ 1/8) · T2 triples fríos propios · T3 rival en racha (≥ 6/8) · T4 rival en racha de triples (≥ 4 de 6) · T5 tiros libres propios ≤ 50 % |
| Jugadores (#244, **hecho**) | J1 rival en racha (≥ 7 puntos en 3 min) · J2 dependencia del rival (> 40 %) · J3 propio en racha · J4 propio frío con volumen · V1 su jugador clave en el banquillo |
| Sanciones y tiempos muertos (#245, **hecho**) | F1 antideportiva/técnica: una más y descalificado · F2 presupuesto de tiempos muertos y rival sin ellos · F4 jugador clave con 4 faltas en cierre igualado · V2 dos rivales con ≥ 3 faltas en pista |
| Cierre y pausas (#246, **hecho**) | C1 briefing de cierre igualado · C3 resumen de fin de cuarto y descanso · C4 gestión de ventaja (+10 con < 5 min) · G1 el rival impone su ritmo |
| Zonas (#247) | Z1 zona caliente propia · Z2 zona fría o mala selección de tiro · Z3 zona que concede el rival · Z4 rival caliente en una zona · Z5 diferencia en la pintura ≥ 10 |
| Quintetos (#248, **hecho**) | R9 quinteto en negativo · J7 +/- individual |
| Alineación y minutos (#271 a #275) | L1 plantilla de FEB en el paquete (**hecho**, #276) · L2 alineación indebida: mínimo de jugadoras de formación en pista, alerta crítica y restricción del recomendador (**integrada**, #272) · M1 descanso de las importantes en partido decidido (**hecho**, #273) · K1 analítica clutch por jugadora (**hecho**, #274) · K2 clutch en el briefing de cierre (**hecho**, #275) |
| Base | tiempos muertos FIBA y contexto del partido (#239, **hecho**: R7 y la base de F2 y C1), propuestas de tiempo muerto y táctica (#240), registro de eventos y ventanas (#237) |

**Aplazadas** (prioridad C): P5 (#249), P6 (#250), J8 (#251), G4 (#252), C2 (#253). **Descartadas** por latencia o falta de datos: 2×1, última posesión, falta intencionada en el último minuto, «falta que dar», detectar la defensa del rival, emparejamientos, quién provoca la falta (la línea de falta solo identifica al infractor) y contraataque.

## Criterios para promover una regla a «validada»
1. Evidencia en **≥ 5 partidos de León** grabados (o ≥ 20 de la competición si es comportamiento de entrenadores), con resultados variados (no solo derrotas).
2. **Precisión** medida con la simulación o el seguimiento: el aviso va seguido de la acción esperada o de una mejora medible en ≥ 40 % de los casos, o su valor está claro aunque la acción no se vea.
3. **Ruido** aceptable: ≤ ~1 aviso por 10 min por regla y sin duplicados.
4. Confirmación del **staff** (umbrales de negocio): se preguntan antes de implementar.
5. Al implementar: TDD (`tests/test_live_core_*`), umbral en `RuleConfig`, regenerar vectores (`python tests/live_vectors/generate.py`) y actualizar LIVE.md y este documento.

## Cómo repetir la evaluación (evaluador de reglas, #238)
`python -m src.live_prep.rule_evaluation --collection <colección FEB> [--recording tests/recordings/<código>.rec.json.gz] [--team <id>] [--config f.json ...] [--feedback f.json ...] --out rule-evaluation` (o `--games-dir <carpeta>` con partidos en JSON). Sin credenciales locales: GitHub → *Actions → Rule evaluation → Run workflow* con la colección; el informe sale en el *Summary* y en el artefacto `rule-evaluation` (`report.md`, `evaluation.json`, `alerts.jsonl`). Detalle del método y de las métricas en [LIVE.md](LIVE.md).
1. Tras cada partido grabado de León: añadir su grabación a `tests/recordings/` (con `recording_pack`, ver LIVE.md) para que sustituya al feed simulado de su partido, y ejecutar el evaluador.
2. Anotar los resultados en un nuevo fichero `docs/evaluaciones/<fecha>.md` (el informe generado, con las conclusiones) y actualizar la tabla de arriba (evidencia y estado).
3. Para probar un umbral o apagar una regla sin tocar el código: un fichero `--config` con `{"name": "...", "rule_config": {"rules_off": ["rival_run"], "run_points": 6}}` se compara con la configuración de serie («base», siempre la línea base) sobre los **mismos** partidos.
4. Con la exportación de feedback de la app (`--feedback`), la tabla «Respuesta del staff» muestra, por regla, cuántas alertas se siguieron, descartaron o ya estaban hechas, y la **obediencia** (seguidas entre seguidas y descartadas).

## Datos que faltan para decidir mejor
- Más partidos grabados de León: depende de que el planner cubra la ventana previa (#205).
- Saber si el staff **vio y usó** las alertas, para pasar de coincidencia a obediencia: la app ya tiene los botones «seguida / descartada / ya hecho» y exporta el resultado (#235, [LIVE.md](LIVE.md)); el evaluador ya lo lee (`--feedback`); falta usarlo en partidos reales.
- Paquete con más partidos previos (líneas base de jugador menos ruidosas).
