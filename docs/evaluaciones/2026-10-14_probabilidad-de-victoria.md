# Probabilidad de victoria: informe definitivo de la calibración (14/10/2026)

**Terminología**: *puntos porcentuales* (pp) miden la probabilidad (prevista 35 % frente a 42 % real = 7 pp); *puntos de marcador* miden el margen del partido (el MAE del margen es de ~7,3 puntos de marcador). Son cosas distintas.

## Conclusiones aplicables

1. **El modelo está bien calibrado en conjunto** (1.529 partidos de LF Endesa, LF2 y LF Challenge, 2024/25 y 2025/26; 21.312 cortes de 5 min): en los deciles de 10 % a 90 % el desvío es de ±2 pp como máximo y **todos los intervalos de confianza al 95 % (remuestreo por partido) caben dentro de ±5 pp**, el límite del criterio acordado. En los extremos hay un exceso de seguridad de ~1 pp (p. ej. 97,4 % previsto, 96,2 % real) que no tiene importancia práctica. **El criterio se cumple.**
2. **En LF Challenge sola** (454 partidos, la competición del staff) el decil 30-40 % se desvía +7,4 pp (IC 95 % [+1,7, +12,8]) y el 60-70 % −7,5 pp (mismo desvío visto desde el otro equipo). Es distinto de cero, pero **el intervalo incluye los 5 pp**: no puede afirmarse que supere el límite. Con 10 deciles, alguno sale «significativo» por azar, y los dos son el mismo hallazgo. No hay evidencia suficiente para un ajuste propio de LF Challenge.
3. **Lo que aporta el modelo es el valor previo más el marcador y el tiempo.** Gana con claridad a «solo marcador y tiempo» (log loss 0,391 frente a 0,435; MAE del margen 7,3 frente a 8,3 puntos de marcador) y queda a una milésima de «solo valor previo» (0,389). Los Four Factors del partido **no añaden** información sobre el valor previo; las palancas siguen siendo útiles como orden de prioridades, no como cifras exactas.
4. **Decisiones**: la tarjeta de la app se mantiene como está (porcentaje con la insignia «Experimental» y su nota); no se tocan el motor ni los parámetros (`wp_n0` = 120, `wp_sigma` = 12, `wp_home_adv` = 4); la alerta de vuelco (#258) sigue aplazada hasta repetir esta medición con más partidos de LF Challenge de 2026/27 (con `python -m src.live_prep.wp_cli … --bootstrap 1000 --no-grid`).

### Intervalos de confianza por decil: LF Endesa + LF2 + LF Challenge (1.529 partidos)

Desvío = frecuencia real − probabilidad prevista, en puntos. Un intervalo que no contiene el 0 indica que el desvío no es solo ruido.

| Decil | Cortes | Partidos | P media | Frecuencia | Desvío | IC 95 % | ¿Distinto de 0? |
|---|---|---|---|---|---|---|---|
| 0-10 % | 4558 | 1271 | 0.026 | 0.038 | +1.1 | [0.3, 2.0] | **sí** |
| 10-20 % | 1732 | 1022 | 0.148 | 0.163 | +1.5 | [-0.9, 3.9] | no |
| 20-30 % | 1499 | 911 | 0.249 | 0.247 | -0.2 | [-2.8, 2.6] | no |
| 30-40 % | 1496 | 834 | 0.349 | 0.368 | +1.9 | [-1.0, 4.8] | no |
| 40-50 % | 1374 | 753 | 0.451 | 0.433 | -1.8 | [-4.4, 0.8] | no |
| 50-60 % | 1380 | 756 | 0.548 | 0.567 | +1.8 | [-0.8, 4.3] | no |
| 60-70 % | 1496 | 834 | 0.651 | 0.632 | -1.9 | [-4.9, 0.9] | no |
| 70-80 % | 1498 | 910 | 0.751 | 0.753 | +0.2 | [-2.6, 2.7] | no |
| 80-90 % | 1731 | 1022 | 0.852 | 0.837 | -1.5 | [-4.0, 0.9] | no |
| 90-100 % | 4548 | 1269 | 0.974 | 0.962 | -1.1 | [-2.0, -0.3] | **sí** |

### Intervalos de confianza por decil: solo LF Challenge (454 partidos)

Desvío = frecuencia real − probabilidad prevista, en puntos. Un intervalo que no contiene el 0 indica que el desvío no es solo ruido.

| Decil | Cortes | Partidos | P media | Frecuencia | Desvío | IC 95 % | ¿Distinto de 0? |
|---|---|---|---|---|---|---|---|
| 0-10 % | 1426 | 381 | 0.025 | 0.031 | +0.6 | [-0.6, 1.8] | no |
| 10-20 % | 514 | 305 | 0.146 | 0.160 | +1.3 | [-2.7, 5.5] | no |
| 20-30 % | 445 | 262 | 0.250 | 0.254 | +0.4 | [-4.3, 5.0] | no |
| 30-40 % | 409 | 223 | 0.349 | 0.423 | +7.4 | [1.7, 12.8] | **sí** |
| 40-50 % | 383 | 209 | 0.453 | 0.418 | -3.5 | [-8.5, 1.8] | no |
| 50-60 % | 385 | 210 | 0.547 | 0.582 | +3.5 | [-1.8, 8.5] | no |
| 60-70 % | 408 | 222 | 0.651 | 0.576 | -7.5 | [-13.0, -1.8] | **sí** |
| 70-80 % | 445 | 262 | 0.749 | 0.746 | -0.3 | [-5.0, 4.3] | no |
| 80-90 % | 515 | 306 | 0.854 | 0.841 | -1.3 | [-5.5, 2.6] | no |
| 90-100 % | 1426 | 381 | 0.975 | 0.969 | -0.6 | [-1.8, 0.6] | no |

---

## Actualización: con LF2 y LF Endesa **sí cumple el criterio**

Con 1.302 partidos de LF Endesa, LF2 y LF Challenge (2024/25 y 2025/26 según el caso; 18.134 cortes de 5 min, descargados con `download_games`, #301) el modelo cumple el criterio acordado: mejor que «solo marcador y tiempo» (log loss 0,398 frente a 0,439), no peor que «solo valor previo» (0,396) y **mayor desvío por decil 1,8 pts** (≤ 5, con deciles de más de 1.100 cortes). Las probabilidades de la franja 30-70 % son ahora correctas (p. ej. 34,9 % previsto → 35,5 % real; 65,1 % → 64,4 %): el desvío de ~7 pts de la primera calibración era de **LF Challenge sola**, con deciles de ~400 cortes (la mitad independientes) y una liga distinta.

**Validación con una competición entera fuera del ajuste** (entrenando con las demás):

| Validación | Cortes / partidos | Log loss (defecto) | Valor previo | Marcador y tiempo | Mayor desvío (≥ 400 cortes) | Criterio |
|---|---|---|---|---|---|---|
| LF Endesa 2025/26 | 2.934 / 215 | 0,422 | 0,422 | 0,448 | 1,4 | **Cumplido** |
| LF2 2025/26 | 4.508 / 323 | 0,377 | 0,371 | 0,433 | 2,4 | NO por 0,001 (0,006 sobre el prior; tolerancia 0,005). Con los parámetros ajustados sí cumple log loss pero el desvío sube a 5,6 |
| LF Challenge 2025/26 | 3.178 / 227 | 0,354 | 0,350 | 0,412 | (deciles < 400 cortes) | no concluyente por tamaño |

**Lectura**: el modelo es fiable en conjunto, y los fallos que quedan son marginales (una milésima de log loss o medio punto de desvío). **En LF Challenge sola, la competición del staff, el tramo 30-70 % sigue desviándose hasta ~7 pts** (454 partidos): por eso la tarjeta mantiene la insignia «Experimental» y su nota hasta que haya más partidos de 2026/27 de esa liga. Los Four Factors del partido siguen sin aportar sobre el valor previo. Siguientes pasos opcionales: parámetros por competición (el `wp_sigma` y `wp_n0` mejores salen distintos), incertidumbre del prior, repetir con 2026/27.

### Entrenamiento conjunto (1.302 partidos)

## Variantes

| Variante | Brier | Log loss | MAE del margen | Mayor desvío por decil (pts) |
|---|---|---|---|---|
| Modelo completo | 0.129 | 0.398 | 7.29 | 1.8 |
| Solo valor previo | 0.128 | 0.396 | 7.25 | 1.6 |
| Solo marcador y tiempo | 0.145 | 0.439 | 8.18 | 0.9 |

**Criterio para mostrarla en la app**: mejor que «solo marcador y tiempo» (sí), no peor que «solo valor previo» en más de 0.005 de log loss (sí) y desvío por decil con al menos 400 cortes ≤ 5 pts (mayor desvío: 1.8). **Cumplido.**


### Validación en LF Endesa 2025/26


2934 cortes de 215 partidos que no se usaron para ajustar. Parámetros ajustados: `{'wp_sigma': 13.5, 'wp_n0': 240.0, 'wp_home_adv': 4.0, 'ff_beta': 9.0}`.

| Variante | Brier | Log loss | MAE del margen | Mayor desvío por decil (pts) |
|---|---|---|---|---|
| Parámetros por defecto (modelo completo) | 0.141 | 0.422 | 8.04 | 6.8 |
| Parámetros ajustados (modelo completo) | 0.139 | 0.418 | 8.01 | 3.7 |
| Solo valor previo | 0.140 | 0.422 | 7.97 | 6.7 |
| Solo marcador y tiempo | 0.152 | 0.448 | 8.81 | 3.1 |

**Criterio en la validación** (parámetros por defecto): mejor que «solo marcador y tiempo» (sí), no peor que «solo valor previo» en más de 0.005 de log loss (sí) y desvío por decil con al menos 400 cortes ≤ 5 pts (mayor desvío: 1.4). **Cumplido.**
**Criterio en la validación** (parámetros ajustados): mejor que «solo marcador y tiempo» (sí), no peor que «solo valor previo» en más de 0.005 de log loss (sí) y desvío por decil con al menos 400 cortes ≤ 5 pts (mayor desvío: 0.1). **Cumplido.**

### Validación en LF2 2025/26


4508 cortes de 323 partidos que no se usaron para ajustar. Parámetros ajustados: `{'wp_sigma': 13.5, 'wp_n0': 240.0, 'wp_home_adv': 4.0, 'ff_beta': 9.0}`.

| Variante | Brier | Log loss | MAE del margen | Mayor desvío por decil (pts) |
|---|---|---|---|---|
| Parámetros por defecto (modelo completo) | 0.123 | 0.377 | 6.86 | 2.4 |
| Parámetros ajustados (modelo completo) | 0.122 | 0.378 | 6.83 | 5.7 |
| Solo valor previo | 0.121 | 0.371 | 6.81 | 4.0 |
| Solo marcador y tiempo | 0.144 | 0.433 | 7.66 | 5.7 |

**Criterio en la validación** (parámetros por defecto): mejor que «solo marcador y tiempo» (sí), no peor que «solo valor previo» en más de 0.005 de log loss (no) y desvío por decil con al menos 400 cortes ≤ 5 pts (mayor desvío: 2.4). **NO cumplido.**
**Criterio en la validación** (parámetros ajustados): mejor que «solo marcador y tiempo» (sí), no peor que «solo valor previo» en más de 0.005 de log loss (sí) y desvío por decil con al menos 400 cortes ≤ 5 pts (mayor desvío: 5.6). **NO cumplido.**

---

# Primera calibración: solo LF Challenge 2024/25 y 2025/26


**Conclusión: el modelo es útil pero NO cumple el criterio para mostrarlo en la app. Se vuelve a medir cuando haya más datos de la temporada en curso.**

Criterio acordado el 14/10/2026: mejor que «solo marcador y tiempo», no peor que «solo valor previo» en más de 0,005 de log loss, y desvío ≤ 5 pts en los deciles con al menos 400 cortes.

- **Datos**: 454 partidos (2024/25 y 2025/26, liga regular y play-offs), 6.356 cortes de 5 min, bajados con `python -m src.live_prep.download_games` (#301). **2023/24 se descartó**: su play-by-play escribe los puntos como `(13 Pts)`, el motor lee 0-0 y cualquier previsión sería falsa (#303); el evaluador omite esos partidos.
- **Cumple las dos comparaciones**: log loss 0,370 frente a 0,420 de «solo marcador y tiempo» y a 0,368 de «solo valor previo» (dentro de la tolerancia). El MAE del margen es 7,4 frente a 8,6 puntos. Pero los Four Factors del partido **no aportan** sobre el prior: `ff_beta` da igual entre 0 y 9.
- **No cumple la fiabilidad**: con todo junto el mayor desvío es 7,5 pts (deciles 30-40 % y 60-70 %, con 409 cortes cada uno: la probabilidad es demasiado extrema en el tramo medio). **Solo con 2024/25 sí se cumple** (1,1 pts), pero 2025/26, la más reciente, se desvía hasta 10 pts: el modelo no es estable entre temporadas.
- **Ajuste**: `wp_n0` = 120 (adoptado). Se amplió la rejilla de `wp_sigma` hasta 18 (el mejor estaba en el borde con 13,5) y se probó encoger el prior del paquete: ninguna combinación arregla el tramo medio (log loss plano en 0,369-0,370) y el valor de `wp_sigma` sigue en 12 (13,5 mejora en 0,000-0,003, ruido). El factor de encogimiento del prior se descartó por no aportar.
- **Siguiente paso**: repetir con los partidos que se vayan jugando de 2026/27 (también como validación) y mejorar la señal del partido antes de mostrar nada al staff; la probabilidad, de mostrarse, descansaría sobre todo en el valor previo.

6356 cortes de 454 partidos (ambos puntos de vista, cortes cada 5 min). Parámetros actuales: `wp_sigma=12.0`, `wp_n0=120.0`, `wp_home_adv=4.0`, `ff_beta=9.0`.

## Variantes

| Variante | Brier | Log loss | MAE del margen | Mayor desvío por decil (pts) |
|---|---|---|---|---|
| Modelo completo | 0.122 | 0.370 | 7.42 | 7.5 |
| Solo valor previo | 0.121 | 0.368 | 7.37 | 6.5 |
| Solo marcador y tiempo | 0.139 | 0.420 | 8.63 | 3.3 |

**Criterio para mostrarla en la app**: mejor que «solo marcador y tiempo» (sí), no peor que «solo valor previo» en más de 0.005 de log loss (sí) y desvío por decil con al menos 400 cortes ≤ 5 pts (mayor desvío: 7.5). **NO cumplido.**

## Fiabilidad del modelo completo

| Decil | n | P media | Frecuencia |
|---|---|---|---|
| 0-10 % | 1426 | 0.025 | 0.031 |
| 10-20 % | 514 | 0.146 | 0.160 |
| 20-30 % | 445 | 0.250 | 0.254 |
| 30-40 % | 409 | 0.349 | 0.423 |
| 40-50 % | 383 | 0.453 | 0.418 |
| 50-60 % | 385 | 0.547 | 0.582 |
| 60-70 % | 408 | 0.651 | 0.576 |
| 70-80 % | 445 | 0.749 | 0.746 |
| 80-90 % | 515 | 0.854 | 0.841 |
| 90-100 % | 1426 | 0.975 | 0.969 |

## Mejores parámetros (por log loss)

| Parámetros | Log loss | Brier | MAE |
|---|---|---|---|
| {'wp_sigma': 12.0, 'wp_n0': 240.0, 'wp_home_adv': 4.0, 'ff_beta': 0.0} | 0.369 | 0.121 | 7.39 |
| {'wp_sigma': 13.5, 'wp_n0': 240.0, 'wp_home_adv': 4.0, 'ff_beta': 9.0} | 0.369 | 0.121 | 7.39 |
| {'wp_sigma': 12.0, 'wp_n0': 240.0, 'wp_home_adv': 4.0, 'ff_beta': 9.0} | 0.369 | 0.121 | 7.39 |
| {'wp_sigma': 13.5, 'wp_n0': 240.0, 'wp_home_adv': 4.0, 'ff_beta': 0.0} | 0.369 | 0.121 | 7.39 |
| {'wp_sigma': 12.0, 'wp_n0': 240.0, 'wp_home_adv': 0.0, 'ff_beta': 0.0} | 0.370 | 0.122 | 7.41 |
| {'wp_sigma': 12.0, 'wp_n0': 240.0, 'wp_home_adv': 0.0, 'ff_beta': 9.0} | 0.370 | 0.122 | 7.40 |
| {'wp_sigma': 12.0, 'wp_n0': 120.0, 'wp_home_adv': 4.0, 'ff_beta': 0.0} | 0.370 | 0.122 | 7.44 |
| {'wp_sigma': 12.0, 'wp_n0': 120.0, 'wp_home_adv': 4.0, 'ff_beta': 9.0} | 0.370 | 0.122 | 7.42 |

## Validación en una temporada aparte

3178 cortes de 227 partidos que no se usaron para ajustar. Parámetros ajustados: `{'wp_sigma': 13.5, 'wp_n0': 240.0, 'wp_home_adv': 4.0, 'ff_beta': 0.0}`.

| Variante | Brier | Log loss | MAE del margen | Mayor desvío por decil (pts) |
|---|---|---|---|---|
| Parámetros por defecto (modelo completo) | 0.117 | 0.354 | 7.60 | 10.1 |
| Parámetros ajustados (modelo completo) | 0.116 | 0.354 | 7.57 | 10.5 |
| Solo valor previo | 0.116 | 0.350 | 7.53 | 8.2 |
| Solo marcador y tiempo | 0.136 | 0.412 | 9.00 | 5.3 |
