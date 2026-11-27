# Historia del motor en vivo (para Claude)
Pasajes movidos de [LIVE.md](../LIVE.md) el 27/11/2026: incidentes, «antes hacía X, ahora Y» y cronología por issue. El estado vigente está en LIVE.md; aquí solo el porqué y lo que se midió entonces.

## Correcciones de líneas del feed en LiveEngine (#1119-#1121)
- **Bug encontrado con esta grabación**: FEB **corrige líneas del PBP mientras se juega** (en este partido: un triple pasó a doble, una sustitución «Entra» pasó a «Sale», los tiros libres de una falta cambiaron) y `LiveEngine` solo detectaba líneas borradas o fuera de orden: el triple corregido conservó su 3.er punto (marcador final 39-59 en vez de 38-59). Ahora cada

## Demos de la app: regeneración del paquete de Zamora–León
- El de Zamora–León se regeneró el 14/10/2026 (8 partidos previos, plantilla de 20 jugadoras, 33 quintetos): el partido pasa de 91 a 102 alertas (zonas propias y concedidas, triples y más fatiga con las bases nuevas).

## Grabador del feed: ventana del planner (#205)
- GitHub ejecutó el `schedule` de 15 min solo 4-5 veces al día (sin ninguna ejecución en los 45 min previos al partido de Zamora, que solo se grabó por lanzamiento manual), así que el planner

## Publicación automática de paquetes: la rama live-packages y Vercel
- sin él, la integración de Git de Vercel intentaba construirla en cada publicación y fallaba (`Root Directory "frontend" does not exist`, correo de aviso)

## Paquete .bpkg: el endpoint retirado en #202
- Lo que describía: equipo propio, rival y contraseña (≥ 8 caracteres, **no recuperable**) → un job en segundo plano que reproducía todos los partidos de la competición con el motor live y servía el `.bpkg` una sola vez, con un único job a la vez y caducidad de 15 min.

## Publicación automática de paquetes: jornadas completas (#286, #172, #450)
- (con una ventana fija de 7 días desde el primer partido sí entraban 2 de 7 en 2ª FEB A). Casos reales que lo motivaron: 2ª FEB B (un partido de la jornada 1 aplazado a diciembre ganaba a la jornada 4 y se publicaría 1 partido) y LF Challenge (la jornada 4 traía un partido del 21/12).

## Feedback de la 0.3.2 en el motor
- Antes mostraba solo el parcial de la ventana como si fuera el marcador.
- Caso real: Copa, final del 3.er cuarto (más rápido que antes y parcial en contra de -12).

## Feedback de la 0.3.2 en la app: avisos de partidos de interés (#482)
- **Hasta la 0.5.2 no funcionaban en ningún dispositivo** (feedback de la 0.5.2, tras #697): `capacitorReminderPlugin` devolvía desde una función `async` el plugin de Capacitor, un `Proxy` que responde a **cualquier** propiedad, `then` incluida; la promesa lo tomaba por otra promesa, llamaba a su `then` (un método nativo que no existe) y no se resolvía nunca, así que ni se pedía el permiso ni se programaba nada ni se abría el partido al pulsar el aviso. Ahora devuelve un objeto simple con los métodos del plugin.

## Efecto de cada regla en Zamora–León (conteos de alertas)
- En Zamora–León salen 3 análisis y 2 seguimientos (80 alertas).
- - **Efecto en Zamora–León** de la fase: ninguno (1 / 10 / 16): en el tramo decidido solo salen faltas y una fatiga que ya era informativa (la regla de descanso de #273 añadió después 4 informativas). El evaluador (#238) permite medir el efecto con más partidos (`--config` con `rules_off: ["game_context"]`).
- - **Zamora–León**: el recuento fijo del test de severidad pasa a una **tabla por regla** (`REAL_MATCH_TABLE`): 64 alertas (4 / 26 / 34). Las de **fatiga** suben (10) porque ahora escalan por nivel y stint; las de **palanca** pasan de 5 a 9 porque el déficit de tiro empeoró de verdad unos 25 puntos por 100 en el partido y cada tramo de 5 se avisa (el tramo es **provisional**: subirlo a 8-10 lo reduciría; decidirlo con el evaluador y el staff).
- - **Zamora–León**: 5 alertas nuevas (2 de P6, 1 de G4 y 2 de C2; P5 y J8 no saltan en ese partido): 87 → 92.
- - **Zamora–León**: 5 alertas nuevas (2 de zona fría propia, 2 de la pintura y la de Pérez Relancio desde la zona): 82 → 87. Z1 y Z3 no saltan: su paquete grabado es anterior a `own` y `rival_conceded` (Z3 necesita el paquete nuevo).
- - **Zamora–León**: 8 alertas nuevas (2 de R9 y 6 de J7): 74 → 82.
- - **Zamora–León**: 3 alertas nuevas, los tres resúmenes (1.er cuarto, descanso con −11 y 3.er cuarto). C1, C4 y G1 no saltan: el partido no se igualó en el cierre, se iba perdiendo y el ritmo no cumplió la condición. K2 (#275, hecho) añade las jugadoras clutch a C1: ver *K2* abajo.
- - **Zamora–León**: 1 alerta nueva (V2, Pérez Relancio y Aspajo con 3 faltas en pista): 70 → 71. No hay sanciones ni final igualado con tiempos muertos por perder en ese partido.
- - **Zamora–León**: 6 alertas nuevas (1 aviso y 5 informativas: la racha de Pérez Relancio, la de Vaquera con 1/6 de tiro y las salidas de Soares): 64 → 70. J2 y J3 no saltan en ese partido.
- - **Zamora–León**: la sequía de 6:19 avisa a los 4:21 (antes del tiempo muerto de León a 3:38 del 2.º cuarto) y otra crítica de 6:12 al seguir seca tras él. En total 14 alertas nuevas (2 críticas contra 1, más avisos e informativas): 1 / 14 / 23 → 2 / 24 / 26; el evaluador (#238) dirá cuántas se siguieron.
- - **Efecto en Zamora–León**: 7 alertas nuevas (4 avisos y 3 informativas): 1 / 10 / 20 → 1 / 14 / 23.
- - **Efecto en Zamora–León** (perdido por 20+): 4 alertas informativas nuevas en el tramo decidido (1 / 10 / 20). Los umbrales (20 min de media, 10 min hoy, 8:00 del 4.º) son **provisionales**: medirlos con el evaluador (#238) y confirmarlos con el staff.
- En Zamora–León desaparece una crítica.
- Efecto en Zamora–León (perdido por 21): 92 → 91 alertas, con más fatiga (10 → 18) y menos del resto.
- En Zamora–León: 1 / 10 / 16 (antes ≈ 1 / 18 / 7, todo naranja).

## Feedback de la 0.3.3 en el motor
- (feedback de la 0.5.2, Valencia–León 2524501: «5 pérdidas propias en los últimos 5 min» a 1:40 del 3.er cuarto eran 3 del final del 2.º y 2 del 3.º, con el descanso en medio)
- (antes «parcial 1-9» a los 30 s de un cuarto era un 1-7 del anterior más una canasta rival)
- : un tiempo muerto abría un episodio nuevo mientras la ventana de 3 min seguía con las **mismas** 4 pérdidas (Cultural–Melilla, 1C). En Zamora–León: `long_run` 3 → 2 y `rival_orb_window` 3 → 2 (75 alertas).
- : las ventanas incluyen los dos extremos y un evento de ese mismo segundo se contaba dos veces (#619, hallado por las invariantes de B1)
- : el Cultural–Oviedo del 21/10 se siguió con un paquete anterior al arreglo de las eliminatorias (#492; 0 en eliminatorias, 2 en la fase de grupos) y conserva su mínimo; los paquetes publicados desde el 22/10 llevan el bueno
- `LiveSession.load_replay` calculaba la duración con el último evento, y la línea de cierre «Fin del Cuarto 4» está justo en el segundo 2400, que es también el inicio del periodo 5: la revisión de un partido sin prórroga duraba 45 minutos y a 300× enseñaba una prórroga que no hubo (el test de la muestra tenía 2700 escrito por el mismo fallo). Ahora esa línea cuenta como el final del periodo que cierra (como ya hacía `replay`).
- - **Llíria sin último cuarto (#519)**: no era un error. En 2536311 la mesa de FEB anotó el 3.er y el 4.º cuarto al final (`LogTimeUtc` del 3.º hasta las 19:34, el 4.º de 19:00 a 19:37): en directo no habrían salido hasta el cierre y la demo, que respeta esa latencia, tampoco; los datos están completos (142 líneas).

## Feedback del staff sobre las alertas: recuento (#314)
- **Recuento (#314, el panel se quitó en #933)**: «X de N alertas valoradas» contaba **solo las alertas de la reproducción en pantalla**; el historial de ejecuciones anteriores del mismo partido sigue en el dispositivo (las respuestas se conservan y vuelven si salta la misma alerta al repetir la reproducción) y en la exportación, pero no entra en el recuento (con 40 alertas en pantalla decía «0 de 53» porque sumaba las de una ejecución anterior más larga). **Decisión (14/10/2026)**: se mantiene la funcionalidad —un panel pequeño y la exportación alimentan `attach_feedback` del evaluador— y se vuelve a valorar con el uso real del staff.

## Registro de eventos y ventanas (#237)
- Antes solo había `pts`, `tov` y `orb` sin jugador (4 elementos); `windows` sigue leyendo esas entradas, sin jugador.
- Al ampliar el registro solo cambió el resumen del `snapshot` en los puntos de control del motor; los de alertas y análisis no (no hay cambio de comportamiento). Con el registro ampliado (unas 330 entradas al final del partido en lugar de unas 130) la actualización en Pyodide sigue en torno a 20 ms.

## Fatiga con poca muestra y suelo absoluto (#479)
- **Fatiga con poca muestra y suelo absoluto (#479, feedback 0.3.2)**: en la demo Cultural–Melilla O. Siquier recibía «riesgo de fatiga muy alto» con 3:35 seguidos: su línea base era de 2 partidos y 4 tramos (tramo habitual 1:48), así que 215 s eran el doble de su tramo y el índice se saturaba. Reglas (umbrales
- (`fatigue_default_avg_stint_s` = **300 s**, antes 420: con 420 s y líneas base de 1 partido la fatiga no saltaba ni con 9:38 seguidos en Zamora–León)
- Con ello Siquier no genera ninguna alerta y Zamora–León conserva 7 (4 avisos, 3 críticas, de 7:44 a 9:47 seguidos).

## El cierre, el resumen y el ritmo (#246): G1
- Sustituye a la regla de «el rival impone su ritmo» (hábitos de ritmo, margen ≥ 5): avisaba con 15 min por delante y tras remontadas hechas subiendo el ritmo.

## Alineación indebida (#272, #481)
- Con la grabación real Cultural–Oviedo (eliminatoria) la regla antigua daba **19 alertas críticas falsas** contra Oviedo (jugó 2/3 del partido con un solo jugador de formación, algo legal en una eliminatoria); con 0 no hay ninguna.

## Probabilidad de victoria: palancas, ataque o defensa (#586)
- hasta entonces el lado solo cambiaba la frase del diagnóstico y la acción y las sustituciones eran siempre las del ataque (en Cultural–Melilla 2536133 la probabilidad caía con «balón» en la defensa —Melilla perdía pocos balones— y se decía «asegurar el balón» proponiendo a quien pierde menos). Ahora, con el lado `defence`:

## Calibración de la probabilidad de victoria (#255)
- **Reevaluación con 24 partidos de 2026/27 (20/10)**: mismo patrón en los deciles 30-40 % (+13,7 pp) y 60-70 % (−13,7 pp) pero sin intervalos que excluyan el 0 y sin valor previo (los ids de equipo cambian cada temporada); criterio no cumplido con esa muestra, sin cambios; [informe](2026-10-20_probabilidad-de-victoria-2026-27.md). **Reevaluación con 235 partidos de 2026/27 (22/10)**: **cumple el criterio** sin mínimo de partidos previos (log loss 0,427 frente a 0,454 de marcador y tiempo y 0,424 del valor previo; desvío máximo 1,6 pp) y el patrón raro del 20/10 desaparece; con ≥ 3 partidos previos solo quedan 81 partidos y el criterio no es evaluable; parámetros sin cambios (ajustar con 765 partidos de 2025/26 y validar en 2026/27 gana 0,003 de log loss); la tarjeta sigue experimental hasta ≈ 250 partidos con valor previo real; [informe](2026-10-22_reevaluacion-2026-27.md) (con la revisión de umbrales de las reglas).

## Partidos finalizados (#407, #557)
- (ya podía ser el siguiente: un finalizado de Caja Rural–Xiria se guardó con el paquete de Getafe–Cultural y no se podía revisar)

## El paquete debe ser el del partido (#417)
- Motivo: con el paquete del León–Zamora sobre el León–Unibasket el rival no anotaba nunca y salían «El rival lleva 30:00 sin anotar» o «Pintura: 30-0».

## FBCYL en directo (#446)
- ; antes el mapa de tiros de FBCYL iba **vacío** y las reglas de zonas callaban, también en los paquetes y en el evaluador

## FBCYL spike (#444)
- Indicio previo: los 11 partidos jugados del grupo A-1 tienen todos sus movimientos con `timestamp` dentro de 12 s, al terminar el partido. **La grabación del 31/10 (UNILEON–VILLAMURIEL) no fue concluyente**: solo sondeaba los endpoints de `msstats`, que necesitan el `universallyid`, y ese id aparece al terminar (calendario «en directo» sin id durante más de una hora; al final, id, marcador y 610 movimientos de golpe).

## Textos de las alertas (#421)
- Revisando las alertas con el staff se vio que casi toda regla con propuesta decía la acción dos veces: como última frase del mensaje y como propuesta (la app la muestra bajo el mensaje; el PDF, al lado). **Convención**:
