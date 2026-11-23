# Índice de formación (#893, E3): resultado del 20/11/2026

**Pregunta**: ¿qué se espera de un jugador de formación (FEB, U12 a U18) en el juego sénior **si llega**, y se puede decir con un rango honesto?

**Método** (`src/market/formation.py`, `scripts/formation_study.py`, no corre en el CI): por sexo y eje, `z_sénior = a + b·z_formación + g·[U18] + ruido` con una cresta (λ = 1) para que los coeficientes no persigan ruido. `z_sénior` es el z de su primera temporada sénior (la siguiente) **en la escala común del grafo** (menos el nivel θ de su competición, E1), de modo que se traduce a cualquier competición sénior sumando su nivel. **Validado una promoción (temporada de llegada) fuera cada vez**: los niveles del grafo y el ajuste se hacen **sin** esa temporada (un test con espía lo vigila), contra «la media de los que llegaron».

## Resultado (685 jugadores con formación y temporada sénior siguiente; 4.304 predicciones eje-jugador)

| Grupo | Error de la media de los que llegan | Error del índice |
|---|---|---|
| Todos | 0,816 | **0,724** (−11 %) |
| U16 | 0,839 | 0,737 |
| U18 | 0,808 | 0,719 |

Cobertura del rango del 80 %: **79,5 %** (anchura media 2,30 z). La edad no se incluye: una vez conocido el grupo no mejora (0,722 → 0,721, medido antes en una sonda con edad).

## Límites y decisiones

1. **Es condicional a llegar**: solo se ven los que llegan al juego sénior con minutos suficientes. El índice dice «si llega, se espera esto», **nunca** «llegará». No hay forma de estimar la probabilidad de llegar con estos datos (los que no llegan no aparecen en ningún fichero sénior).
2. **El rango es ancho** (±1,15 z): la formación predice menos que el juego sénior de un año a otro. Es información de scouting, no una nota.
3. **Solo FEB**: la formación de FBCYL tiene su propia escala y no está enlazada con esta.
4. **Solo la temporada siguiente**: 685 pares; dos temporadas de salto (U16 → sénior a los 18) quedarían con muy pocos casos.
5. Pendiente (E3b): publicarlo como `formation` en `talent-data` con su `usable` y enseñarlo en la ficha de un jugador de formación («Si llega al sénior»), con el mismo rango y avisos que E4.
