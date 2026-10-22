# Diferencia entre divisiones, medida con la Copa de España (22/10/2026)

Cierra [#503](../LIVE.md) (resto de #464). Un paquete entre equipos de divisiones distintas (Cultural Leonesa de 2.ª FEB contra Alimerka Oviedo de 1.ª) comparaba ratings medidos contra rivales de su propia división. Para ponerlas en la misma escala hacen falta partidos entre divisiones: los de la **Copa de España** (fase de grupos y eliminatorias).

## Datos
Cargados en el MongoDB local con el refresco por competición (`run_atlas_refresh.py --config <un fichero con la Copa, Primera FEB o Segunda FEB de la temporada>`; las ediciones pasadas, `t=2025` y `t=2024`): Copa, Primera FEB y Segunda FEB de 2025/26 y 2024/25, más lo que ya había de 2026/27. **Tercera FEB no se cargó de las temporadas pasadas**: ningún equipo de 3.ª jugó la Copa hasta esta temporada (Marín es el único; sus 3 partidos de 2026/27 entran en la medición).

Cada equipo tiene un rating (media del rating neto por 100 posesiones de sus partidos dentro de su división, en su temporada: los ids cambian cada año) y cada partido entre divisiones aporta `(margen real − diferencia de ratings) / niveles de diferencia`.

## Resultado (`python -m src.live_prep.level_gap --season 2026 --season 2025 --season 2024`)
| Muestra | Partidos | Diferencia por división (por 100 posesiones) | Error típico |
|---|---|---|---|
| **Todas** | **58** | **+23,0** | **2,3** |
| 2024/25 | 39 | +26,3 | 2,9 |
| 2025/26 | 10 | +17,7 | 4,0 |
| 2026/27 | 9 | +14,4 | 4,8 |
| 2.ª–1.ª FEB | 55 | +23,4 | 2,3 |
| 3.ª–2.ª FEB | 3 | +15,4 | 11,2 |

Con corrección por ventaja de campo (4 por 100 posesiones al local) sale +24,0. Los ratings de 2026/27 salen de 3-5 partidos y son más ruidosos, lo que acerca el resultado a 0.

**Validación fuera de muestra** (error absoluto medio del margen por 100 posesiones de los partidos entre divisiones):

| Entrenado con → probado en | Sin ajuste | Mitad del prior | Con la diferencia entrenada | Con 23 |
|---|---|---|---|---|
| 2024 → 2025 | 17,8 | 15,0 | 13,0 | 11,7 |
| 2025 + 2026 → 2024 | 27,3 | 27,8 | 15,4 | 13,7 |

## Decisión (usuario, 22/10/2026)
`category_strength.LEVEL_GAP_NET_RTG = 20,0` (algo por debajo de la estimación agrupada, porque la temporada en curso sale menor y sus ratings son ruidosos). El rating neto del prior se desplaza 20 por división de diferencia; los Four Factors se reducen siempre a la mitad. Reevaluar cuando haya Copa de 2026/27 completa (eliminatorias) y con ratings de temporada avanzada.
