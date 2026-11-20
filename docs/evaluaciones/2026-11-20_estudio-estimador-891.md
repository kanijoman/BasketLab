# Estudio del estimador de equivalencias (#891, E1b)

Parte de la épica #872 (Talent). Resultado de `scripts/equivalence_study.py` sobre lo publicado hoy (`talent-data`: 12.515 observaciones, **1.135 movimientos** entre competiciones en temporadas consecutivas, 4.641 jugadores que se quedan). El estimador es `src/market/equivalence_model.py` y la validación `src/market/equivalence_study.py` (con sus tests); el diseño, [aquí](2026-11-20_grafo-equivalencias-891.md).

## Qué se estima
Por eje del radar, `z_B = ρ · z_A + (θ_B − θ_A) + ruido`: `ρ` la fiabilidad (de los que se quedan, por sexo), `θ` el nivel de cada competición, **ajustado con todos los movimientos a la vez** por mínimos cuadrados, con los errores típicos **agrupados por persona** (el estimador de la varianza CR1). Una arista exige 40 personas distintas; hombres y mujeres, grafos aparte. La respuesta es siempre un **rango** del 80 %: el ruido de un jugador que el modelo no explica más la incertidumbre del cambio de nivel.

## Resultado: una temporada fuera cada vez
Cada temporada se predice con un modelo ajustado **sin ningún movimiento ni quedado que la toque** (7.600 predicciones por eje y movimiento):

| | Error medio de z | |
|---|---|---|
| No traducir (`z_B = z_A`) | 0,742 | |
| Solo encoger por la fiabilidad (`ρ · z_A`) | 0,648 | |
| **El modelo** | **0,598** | −19 % frente a no traducir, −8 % frente a encoger |
| **Intervalo del 80 %: acierta** | **79,7 %** | anchura media 1,90 z |

Por pares (error del modelo frente a no traducir; cobertura): LF2 ↔ LF Challenge 0,577 frente a 0,697, 81 %; LF Challenge ↔ LF Endesa 0,631 frente a 0,801, 78 %; Segunda ↔ Primera FEB 0,583 frente a 0,707, 81 %; Tercera ↔ Segunda FEB 0,626 frente a 0,812, 77 %; el salto de dos niveles LF2 ↔ LF Endesa (184 predicciones, componiendo por Challenge) 0,646 frente a 1,020, 79 %. **Los saltos largos funcionan**: el ajuste conjunto los compone con su intervalo.

Por eje: la mejora es grande en **puntos** (0,978 → 0,650) y **acierto** (1,003 → 0,721); pequeña en asistencias, rebotes y tapones; y **nula en robos y pérdidas** (el modelo da lo mismo que encoger: casi no hay cambio de nivel en esos ejes). La cobertura de cada eje está entre 78 y 81 %.

## Resultado: solo con el pasado (walk-forward)
Predecir 2025 con solo las temporadas anteriores (2.688 predicciones): error del modelo **0,635** frente a 0,797 sin traducir y 0,692 solo encogiendo; el intervalo acierta el **75,9 %**. Algo bajo (no cumple el 80 %, dentro del margen de 5 puntos): con menos historia y una temporada distinta, el ruido real es algo mayor que el estimado. **Lo importante: no hay fuga**, y la ganancia se mantiene.

## Lo que no ayuda (probado)
- **Pendiente libre** (la que muestran los que se mueven en lugar de la fiabilidad): error 0,599 y cobertura 79,7 %, **idénticos**. Se queda la fiabilidad, que es más simple. (El caso de las asistencias de Alicia Flórez parece ruido de una persona, no un efecto general.)
- **Minutos por partido en la competición de origen**: explica casi nada del error (el error medio baja de 0,588 a 0,587 incluso dentro de la muestra). Lo que sí se relaciona con el error es el **papel en la competición de destino** (la correlación del residuo de puntos con los minutos por partido allí es +0,27), que **no se conoce** al predecir. Es la parte de «papel» que el rango tiene que llevar.
- **Edad**: no se puede probar todavía. Las filas publicadas no traen la edad (`age` vacío en todas las de los movimientos); la fecha de nacimiento sí está para muchos. Pendiente para E2, que la necesita igual.

## Veredicto
**El rango se puede enseñar**: el modelo gana a las dos líneas base y su intervalo del 80 % acierta el 79,7 % (la regla del diseño: ganar a las líneas base y estar a ±5 puntos del nominal). Reservas, que van a la ficha:
1. **Anchura**: el rango del 80 % mide ±0,95 z de media (unos ±30 puntos de percentil): sirve para ubicar al jugador, no para ordenarlo con precisión.
2. **El papel**: el cambio de minutos y de uso en la nueva competición es lo que más se sale. E4 puede ofrecerlo como una pregunta explícita (los minutos por partido que se esperan allí), como ya hace la proyección «¿Y si…?» con sus condiciones, en vez de esconderlo en el ancho.
3. **Pocos movimientos**: pares con menos de 100 predicciones (Liga U ↔ Segunda, Primera ↔ Tercera) quedan con cobertura inestable (68 %, 88 %); la arista exige 40 personas, pero con una temporada fuera algunas quedan justas. Conviene que E1c publique el número de personas de cada arista junto a su nivel.
4. **Robos y pérdidas** no cambian con el nivel de la liga: la traducción de esos ejes es solo el encogimiento.

## Siguiente
**E1c**: publicar `equivalences.json` en `talent-data` (versión del método, nodos, `θ` y su covarianza por eje y sexo, `ρ`, las personas de cada arista y el veredicto con su cobertura), con su contrato Python y TypeScript generado. La cuenta de traducir en el navegador (con vectores de paridad) y su uso en la ficha y en el encaje son **E4**.
