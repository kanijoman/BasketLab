# Calibración de umbrales del motor live

**Estado (20/10)**: aplicadas las propuestas 1-4 (#426) y la regla `first_half_timeouts` (#427, candidatas 1 y 2 fundidas: el cierre de Q4 ya lo cubren `timeout_budget` y `closing_briefing`). **Aplazadas** la 5 (sequías) y la 6 (`wp_flip_drop`) hasta tener feedback del staff (#235) o ≥ 5 partidos de León con histórico. Con más de una temporada evaluada la muestra se da por representativa: **la evaluación de reglas queda cerrada**; el feedback posterior se anota regla a regla.

## 1. Qué es y cómo leerlo

Se reproducen partidos terminados «como si fueran en vivo», desde los dos lados, con el motor actual, paquetes construidos solo con partidos anteriores, latencia 42 s (medida real, #411) y sondeo de 10 s. Después se repite con variantes de `RuleConfig` sobre los **mismos** partidos y se compara con la línea base.

| Muestra | Partidos | Equipo-partidos | Uso |
|---|---|---|---|
| LF Challenge 2023-24 a 2025-26 | 753 | 1.362 | línea base global |
| LF Challenge 2025-26 + comparaciones | 275 | 454 | barrido de umbrales (21 configuraciones) |
| León 2026-27 (24 partidos) + 2 grabaciones reales | 24 | 3 | contraste (solo 3 con histórico) |

Métricas por regla: alertas, por equipo-partido y por 10 min, severidad, **duplicados** (misma alerta en 10 min), **seguida** (el equipo hace lo que proponía en ≤ 120 s) y cobertura de tiempos muertos.

### Límites (importan para decidir)
- **Seguida = coincidencia, no obediencia.** Hasta tener el feedback exportado de la app (#235) no sabemos si el staff las habría seguido.
- La conducta del entrenador sale de otras plantillas: son hipótesis, no conclusiones.
- El feed simulado usa el reloj de juego, no `LogTimeUtc`, salvo en 3 equipo-partidos: el retraso real (mediana 42 s, p90 60 s) está aproximado.
- Los ids de equipo cambian cada temporada (2026-27 usa 1008xxx): con `--min-prior-games 3` esos partidos no entran; solo León se evaluó aparte con `--min-prior-games 0`. **Los resultados de León (3 equipo-partidos) no sirven para validar nada.**
- En las primeras jornadas los paquetes tienen poco histórico y inflan el volumen: 80 alertas por equipo-partido en 2025-26 frente a 57,5 en la muestra global. Los 755 partidos dan el orden de magnitud; el criterio de 5 partidos de León sigue sin cumplirse.

## 2. Resultado global

- Línea base global: **57,5 alertas por equipo-partido (14,3 por 10 min)**; en 2025-26: 80,1 (19,9 por 10 min). Criterio de ruido: ≤ ~1 por 10 min **por regla**.
- Reglas por encima de 1 aviso/10 min en 2025-26: `fatigue_high` 2,89 · `rival_foul_trouble` 1,07 · `rival_hot_player` 1,05.
- Seguimiento (≤ 120 s) muy por debajo del 40 % exigido en **todas** las reglas con propuesta medible: `fatigue_high` 33 %, `rest_starters` 31 %, `four_factors_lever` 24 %, `foul_trouble` 19 %, `rival_run` 16 %, `turnover_streak` 14 %, `long_run` 14 %, `own_drought` 4 % (muestra global).
- Duplicados altos (> 40 % de la regla): `rival_foul_pair` 53 %, `paint_battle` 52 %, `four_factors_lever` 50 %, `comeback_plan` 45 %, `turnover_streak` 44 %, `cold_fg_streak` 43 %, `period_edge_deficit` 40 %.

Lectura: el seguimiento bajo es en parte esperable (muchas reglas no proponen una acción verificable en 2 min), pero ninguna regla de acción llega al 40 %. Ninguna está lista para pasar a «validada» con estos datos.

## 3. Clasificación por regla

| Regla | Volumen (/10 min) | Duplicados | Seguida | Veredicto |
|---|---|---|---|---|
| `fatigue_high` | 1,67 global · 2,89 en 2025-26 | 35 % | 33 % | **Subir umbral** (ver 4) |
| `rival_foul_trouble` | 0,72 · 1,07 | 0 % | — | Dejar; vigilar volumen temprano |
| `rival_hot_player` | 0,67 · 1,05 | 0 % | — | Dejar; vigilar volumen |
| `four_factors_lever` | 0,60 | 52 % | 24 % | **Subir umbral/enfriar** (duplicados) |
| `rival_run` / `long_run` | 0,52 / 0,15 | 30 % / 31 % | 16 % / 14 % | Dejar (ver 4: endurecer baja seguimiento) |
| `turnover_streak` | 0,37 | 43 % | 14 % | **Subir umbral** (5) |
| `own_drought` | 0,44 | 42 % | 4 % | Más datos; no tocar al alza ni a la baja |
| `fg_drought` / `rival_drought` | 0,30 / 0,20 | 32 % / 33 % | — | Subir (sequía larga) o dejar |
| `cold_fg_streak` / `cold_3p_streak` | 0,35 / 0,27 | 41 % / 23 % | — | **Subir umbral** (rachas estrictas) |
| `paint_battle`, `rival_foul_pair`, `comeback_plan` | 0,4 / 0,27 / 0,11 | 50 %+ | — | **Enfriar** (más cooldown o umbral) |
| `lineup_net` | 0,06 | 5 % | — | Dejar (pocos avisos y Δ neto +6,7) |
| `win_flip` / `pace_control` | 0,36 / 0,07 | 28 % / 3 % | — | `pace_control` casi no sale con la palanca estricta: más datos |
| Resto (`rival_zone`, `own_zone_*`, `rest_starters`, `closing_briefing`…) | < 0,5 | bajos | `rest_starters` 31 % | Dejar |

## 4. Barrido de umbrales (275 partidos, 454 equipo-partidos; total base 36.358 alertas)

| Grupo | Variante | Efecto | Seguida | Lectura |
|---|---|---|---|---|
| Fatiga | alert 80 (warning 80 es lo actual) | `fatigue_high` 5.265 → 2.074 (−61 %); duplicados 1.899 → 547 | 33 → 34 % | **Mejor opción**: 1,14/10 min, el mismo seguimiento |
| Fatiga | alert 80 / warning 90 / crit 97 | 2.561 | 34 % | Menos reducción, sin ganancia |
| Fatiga | 70/85/97 | 3.642 | 35 % | Insuficiente (aún > 2/10 min) |
| Fatiga | 50/70/90 (laxa) | 7.449 | 32 % | Descartar |
| Parcial rival | run 10 / info 8 / long 12 | `rival_run` −67 %, `long_run` −58 % | 16 → 13 %, 14 → 10 % | **Descartar**: pierde seguimiento |
| Parcial rival | run 6 / info 5 / long 8 | `rival_run` +61 % | 16 → 17 % | Sube volumen sin mejorar nada |
| Sequías | corta (210/180/150) | +701 alertas | `own_drought` 17 → 19 % | Poco seguimiento ganado |
| Sequías | larga (300/270/240) | −832 | `own_drought` 17 → 19 % | Menos ruido sin perder seguimiento: **posible** |
| Rachas de tiro | estrictas (7/5, frías 0 fallos) | −1.675; duplicados casi a 0 | — | **Recomendable** para bajar duplicados |
| Rachas de tiro | laxas | +2.562 | — | Descartar |
| Pérdidas | turnover_streak 5 | 1.022 → 463; dups 445 → 139 | 14 → 14 % | **Bajar ruido sin perder seguimiento** |
| Pérdidas | turnover_streak 3 | 1.022 → 1.799 | 14 → 12 % | Descartar |
| Zonas | pps 0,7 · 7 intentos · pintura 14 | −1.197; `paint_battle` dups 400 → 198 | — | **Recomendable** para zonas |
| Quintetos | lineup_net 8 · 240 s | `lineup_net` 171 → 34 | — | Dejar (la regla ya es poco ruidosa) |
| Faltas | `foul_min_left_s` 480 / 240 | −127 / +115 `foul_trouble` | 18 → 18 % | Sin efecto relevante: **dejar 360** |
| Probabilidad | `wp_flip_drop` 0,25 + lever 0,02 | `win_flip` −28 %, `pace_control` −166 (casi apagada) | — | Probar solo `wp_flip_drop` |
| Modos | `aggressive` | +7.613 (+21 %) | sin cambio | Más ruido, mismo seguimiento |
| Modos | `conservative` | −6.450 (−18 %) | `long_run` 14 → 10 % | Menos ruido, pierde algo de seguimiento |

## 5. Propuestas (necesitan tu visto bueno)

| # | Regla | Parámetro | Actual | Propuesto | Evidencia | Confianza |
|---|---|---|---|---|---|---|
| 1 | `fatigue_high` | `fatigue_alert_index` | 60 | **80** | −61 % alertas, 1,14/10 min, dups −71 %, seguimiento igual (34 %) | **Alta** |
| 2 | `turnover_streak` | `turnover_streak` | 4 | **5** | −55 % alertas, dups −69 %, seguimiento igual (14 %) | Media-alta |
| 3 | Rachas de tiro | `hot_fg_min_made` / `hot_3p_min_made` / `cold_*_max_made` | 6 / 4 / 1 | **7 / 5 / 0** | −1.675 alertas, dups casi eliminados | Media (sin medida de seguimiento) |
| 4 | Zonas | `zone_pps_excess` / `zone_min_attempts` / `paint_diff` | 0,5 / 5 / 10 | **0,7 / 7 / 14** | −1.197, dups de `paint_battle` −50 % | Media |
| 5 | Sequías | `drought_own_s` / `drought_rival_s` / `drought_fg_s` | 240 / 210 / 180 | **300 / 270 / 240** | −832 alertas, `own_drought` seguimiento 17 → 19 % | Baja-media |
| 6 | `win_flip` | `wp_flip_drop` | 0,20 | **0,25** (no tocar `wp_lever_min_gain`) | −28 % de `win_flip`; la palanca 0,02 apaga `pace_control` | Baja |

No se propone tocar: parcial rival (`run_points` 8), quintetos, faltas (360 s), ni cambiar de modo.

## 6. Cobertura y reglas nuevas

2.979 tiempos muertos reales; **829 (28 %)** tuvieron alerta con propuesta de tiempo muerto en los 120 s previos.

| Situación antes del tiempo muerto | n | Con alerta |
|---|---|---|
| Parcial rival neto ≥ 6 en 150 s | 689 | 45 % |
| 3+ pérdidas propias en 5 min | 1.072 | 39 % |
| 2+ triples rivales en 150 s | 417 | 37 % |
| Últimos 2 min del periodo | 1.094 | 21 % |
| Sin patrón claro | 732 | 19 % |

Reglas que más cubrieron: `rival_run` 464, `turnover_streak` 240, `closing_briefing` 129, `long_run` 111, `timeout_budget` 106.

Conducta de los entrenadores (753 partidos): 2,20 tiempos muertos por equipo-partido; solo el 5 % llega tras 8 puntos rivales sin respuesta; 23 % tras +6 neto; 16 % tras 4 pérdidas. **Casi todos los tiempos muertos del último periodo se concentran en los 2 últimos minutos**: 545 del Q4 y 516 del Q2 frente a 59–64 de Q1/Q3. En la primera parte, 561 de 1.506 equipo-mitades no usan ninguno.

Candidatas a regla nueva (la 1 y la 2 se implementaron como `first_half_timeouts`; la 3 queda como idea):
1. **Último minuto de cuarto/mitad con tiempos muertos disponibles** (cierre de Q2 y Q4). 21 % cubierto hoy y es donde los entrenadores los gastan: aviso «tiempo muerto disponible: diseñar la última posesión / evitar el 2-for-1». Horizonte > 42 s: viable.
2. **Tiempo muerto no usado en la primera parte** (37 % de las mitades sin ninguno): recordatorio antes del cierre del Q2 de que se llega con los 2 sin gastar. Solapa con `timeout_budget`; revisar antes si basta ajustarlo.
3. **Dos o más triples rivales en 150 s** (417 casos, 37 % cubiertos): quizá reutilizable `rival_3p_streak` (0,08/10 min, dups 21 %) con umbral más bajo en vez de regla nueva.

## 7. Reproducir

```
git status --short                       # sin cambios salvo este informe y el PDF
PYTHONPATH=".;src" python -m src.live_prep.rule_evaluation --games-dir data/historical_games/lf_challenge \
  --recording tests/recordings/2524470.rec.json.gz --recording tests/recordings/2524475.rec.json.gz \
  --latency 42 --poll 10 --min-prior-games 3 --out <dir>/eval-base
# barrido: añadir --config <dir>/cfg/<nombre>.json  ({"name": "...", "rule_config": {...}}) sobre los mismos partidos
# León 2026-27: --team 1008631 --min-prior-games 0
```
Los JSON de las configuraciones están en el scratchpad de la sesión (ver tabla de la sección 4 para los valores).
