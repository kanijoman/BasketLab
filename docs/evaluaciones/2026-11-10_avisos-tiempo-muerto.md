# Reevaluación de los avisos de tiempo muerto (#524)

La issue (23/10/2026) mantuvo `timeout_review` y `timeout_followup` como estaban tras medir 236 partidos de 2026/27 (1,65 y 0,81 avisos por 10 min) y dejó pendiente reevaluarlos con más partidos reales y el feedback del staff (#235): si el volumen molesta, subir `timeout_run_net`/`timeout_tov_n`, no repasar los tiempos muertos sin motivo claro o limitar el seguimiento; y comprobar que los motivos coinciden con lo que el staff cree.

## Qué se midió
**571 partidos de las 14 competiciones FEB de 2026/27 que hay en el archivo** (LF Challenge, LF Endesa, LF2 A/B, Liga U A/B, Primera FEB, Segunda FEB A/B y cinco grupos de Tercera FEB), con el evaluador de reglas (`python -m src.live_prep.rule_evaluation --games-dir`), cada partido desde los dos equipos y con las reglas de hoy, y la configuración base frente a dos variantes: `quiet` (`timeout_run_net` 8 en vez de 6 y `timeout_tov_n` 4 en vez de 3, lo que sugería la issue) y `no_followup` (`timeout_followup` apagada). 572 equipo-partidos evaluados (el mínimo de 3 partidos previos deja fuera los primeros) y 2.288 bloques de 10 minutos. Cada competición se evaluó aparte, porque la «temporada» que acumula el motor es la de su competición.

## Resultado
| | Tiempo muerto: repaso | Tiempo muerto: seguimiento | Suma | Todas las reglas (con informativas) | Solo críticas y de aviso |
|---|---|---|---|---|---|
| **Hoy, 571 partidos** | **1,71** por 10 min (6,9 por equipo-partido) | **0,76** (3,0) | **2,47** | 41,6 | 18–20 |
| Femeninas (6 competiciones, 224 partidos) | 1,66 | 0,73 | 2,39 | 39,8 | 18,1 |
| Masculinas (8, 347) | 1,75 | 0,78 | 2,53 | 42,8 | 20,1 |
| 23/10 (236 partidos) | 1,65 | 0,81 | 2,46 | «20,0» | — |

- **El volumen no ha cambiado** con 2,4 veces más partidos, y por competición oscila poco: 1,35–2,02 repasos y 0,58–0,94 seguimientos por 10 min.
- **El «total 20,0» del 23/10** coincide con contar solo las alertas críticas y de aviso (18–20); las dos reglas de tiempo muerto son **informativas**, así que no están en ese total y suman unos 2,5 por 10 min sobre unas 40 alertas con las informativas (≈ 6 %). No se ha podido comprobar con qué definición se calculó entonces ese 20,0.
- **Un tiempo muerto de cualquiera de los dos equipos recibe un repaso**, así que el volumen es el número de tiempos muertos del partido (≈ 7 por equipo-partido entre propios y del rival) más el seguimiento (≈ 3).

## Lo que dice de las palancas de la issue
1. **Subir `timeout_run_net` y `timeout_tov_n` no baja el volumen**: la variante `quiet` da **exactamente las mismas alertas** que la base en las 14 competiciones (3.922 repasos y 1.738 seguimientos). Esos umbrales solo deciden **qué motivo se escribe** («para cortar nuestro parcial» frente a «sin motivo claro»), no si hay aviso. La issue suponía otra cosa.
2. **No repasar los tiempos muertos sin motivo claro**: son el **15,2 %** de los repasos (595 de 3.922), es decir −0,26 por 10 min. Poco.
3. **Limitar el seguimiento**: apagarlo quita 0,76 por 10 min (31 % de los avisos de tiempo muerto). Y su veredicto es **«Sin efecto claro» en el 54 %** de los casos (946 de 1.738; «Ha funcionado» 18 %, «No ha funcionado» 16 %, y otro 12 %: los seguimientos de un tiempo muerto del rival, «el rival ha respondido»), así que más de la mitad de los seguimientos no dicen nada decisivo. Es la palanca con más recorrido si hubiera que reducir.

**Motivos de los 3.922 repasos**: última posesión del cuarto 21,6 %, parcial 21,2 %, sequía 16,9 %, sin motivo claro 15,2 %, marcador en contra 9,4 %, el rival anota casi todo 6,3 %, fatiga 5,7 %, pérdidas 3,7 %.

## Lo que esta medición no puede decir
- **Si el volumen molesta al staff**: no hay exportación de feedback de la app (`--feedback`, #235) en el repositorio; ningún dato de uso real. Sin él, 2,5 avisos por 10 minutos, todos informativos, no es una cifra alta, pero que moleste o no es una cuestión del staff.
- **Si los motivos coinciden con lo que el staff cree**: se necesita contrastarlos con el criterio de quien llama el tiempo muerto (una muestra de partidos revisada a mano o su feedback). Los motivos se leen de los 120 s anteriores con umbrales provisionales, y no se ha validado ninguno.

## Recomendación
**Mantener las dos reglas como están**: el volumen es estable, pequeño y todo informativo. La única mejora que los datos respaldan sin esperar al staff, **si se decide**, es que el seguimiento solo avise cuando el veredicto sea claro (o el rival haya respondido), lo que quita el 54 % de los seguimientos (−0,41 por 10 min) sin perder información. La issue sigue aplazada con un disparador concreto: que el staff diga que molestan o aporte feedback de la app.

## Cómo repetirlo
Descargar del archivo privado el fichero `<colección>.jsonl.gz` de cada competición (una carpeta de partidos por competición), convertirlo a un documento FEB por partido (`unwrap_extended_json` de `live_core.vectors`) y lanzar `PYTHONPATH=".;src" python -m src.live_prep.rule_evaluation --games-dir <carpeta> --config quiet.json --config nofollow.json --out <salida>`, con `quiet.json` = `{"name": "quiet", "rule_config": {"timeout_run_net": 8, "timeout_tov_n": 4}}` y `nofollow.json` = `{"name": "no_followup", "rule_config": {"rules_off": ["timeout_followup"]}}`. Cada competición tarda ≈ 1 minuto.
