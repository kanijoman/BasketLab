# Prueba del método de equivalencias con carreras reales (#891)

Parte de la épica #872 (Talent). Primera prueba, **antes de E1b**, con las filas publicadas hoy (`talent-data`, 93 competiciones) y dos carreras propuestas por el usuario: Alicia Flórez Getino (`feb:2099031`) e Isaac Vázquez Pérez (`feb:1778999`). Se ajusta el modelo del [diseño](2026-11-20_grafo-equivalencias-891.md) para cada par de niveles vecinos y se predice, **sin el jugador en el ajuste**, lo que hizo al subir. El script es `scripts/equivalence_pilot.py` (sondeo, no el estimador: E1b lo hará con tests, el grafo completo y el estudio walk-forward).

## Modelo del sondeo
`z_B = ρ_eje · z_A + (θ_B − θ_A)`, con z el percentil como normal, `ρ` la fiabilidad del eje (de los que se quedan en la competición dos temporadas seguidas) y `θ_B − θ_A` el cambio de nivel (de los que se mueven, en los dos sentidos a la vez). El intervalo del 80 % es ±1,28 desviaciones de lo que el modelo no explica.

## ¿Mide bien en general? (todos los que se movieron, dejando fuera a cada persona)
| Par | Movimientos | Error medio de z: sin traducir | solo ρ | **modelo** | El intervalo del 80 % acierta |
|---|---|---|---|---|---|
| LF2 ↔ LF Challenge | 337 | 0,70 | 0,61 | **0,57** | 80 % |
| LF Challenge ↔ LF Endesa | 123 | 0,80 | 0,70 | **0,63** | 80 % |
| Segunda ↔ Primera FEB | 283 | 0,71 | 0,63 | **0,58** | 80 % |
| Tercera ↔ Segunda FEB | 225 | 0,83 | 0,71 | **0,62** | 79 % |

- El modelo reduce el error un **15–25 %** frente a no traducir y un 5–12 % frente a solo encoger por la fiabilidad.
- **Los intervalos están calibrados**: el del 80 % contiene lo real el 79–80 % de las veces en los cuatro pares. Eso es lo que decide que se pueda enseñar un rango.
- Los cambios de nivel concuerdan con la señal de antes: al subir, los puntos caen entre 0,5 y 0,9 z (el acierto, entre 0,3 y 0,6) y los rebotes, robos y tapones casi no cambian.

## Alicia Flórez Getino (nacida en 2004)
Lo que hay en los datos: Campeonato de España júnior (Coterram Generación B.F., 2020 y 2021), **L.F.-2 con B.F. León** (2021), **LF Challenge** (La Cordà de Paterna, 2022 a 2024), **LF Endesa** (Valencia 2023, 2024 y 2026; Durán Maquinaria Ensino, 2025). Con minutos suficientes en ambos lados y temporadas consecutivas hay **dos pasos comprobables**, los dos de LF Challenge a LF Endesa:

| Paso | Ejes dentro del intervalo | Lo que se salió |
|---|---|---|
| Challenge 2023 → Endesa 2024 | 5 de 8 | **Puntos** (esperado z −0,07, real −1,13), **asistencias** (+0,05 esperado, +1,31 real) y **robos** (+0,63 esperado, +1,72 real) |
| Challenge 2024 → Endesa 2025 | **8 de 8** | nada; puntos 0,04 y robos 0,02 de error, frente a 1,19 y 0,94 sin traducir |

- En el segundo paso el modelo acierta con precisión los puntos (esperado z +0,13, real +0,17), los robos y el acierto. Es el caso en que se juega más (1.088 minutos en Endesa).
- En el primero, el cambio de puntos (de +1,06 a −1,13) es mucho mayor que el del nivel: **jugó 362 minutos en Endesa** (suplente en Valencia). El modelo mide el nivel, no el papel: un jugador que casi no tira baja sus puntos y su acierto aunque su capacidad no cambie.
- Sus asistencias y robos **no bajan al subir**, y el modelo los encoge hacia la media (asistencias: esperado z +0,84, real +1,63). Hay habilidades que se mantienen al cambiar de liga y otras que no: **E1b debe medir por eje cuánto se conserva**, además de la fiabilidad.

## Isaac Vázquez Pérez (nacido en 2004)
En los datos: **Segunda FEB 2024 con Cultural y Deportiva Leonesa** (454 minutos) y **Primera FEB 2025** (623 minutos) con el equipo que figura como **Cloud.Gal Ourense Baloncesto**; el usuario recordaba Obradoiro. Un solo paso comprobable, **Segunda → Primera FEB**: **4 de 8 ejes** dentro del intervalo.

- Dentro: puntos (esperado −0,22, real −0,01), tapones, acierto y pérdidas.
- Fuera: **rebotes ofensivos y defensivos** (de −1,55 y −0,73 en Segunda a +0,14 y +0,21 en Primera) y **robos** y **asistencias**. Un cambio así de rebotes no es de nivel: es de **posición o de papel** (más minutos cerca del aro). Con 22 y 32 partidos de muestra pequeña, el ruido también cuenta.

## Lo que no se pudo comprobar (y por qué)
- **ACB (Girona)**: ACB no está cargada (sus ediciones están pausadas): no hay nodo de ACB.
- **Tercera FEB con Bosco Salesianos**: solo están cargadas las temporadas 2024 y 2025 de Tercera FEB (faltan las tandas 4 y 5 de #876), y su paso por Tercera fue antes.
- **Formación y selección** (el Campeonato de España júnior, las selecciones españolas de FIBA): la formación queda fuera de E1 (es de E3) y la selección absoluta no está cargada para ella. Su paso de L.F.-2 a Challenge (2021 a 2023) no es consecutivo con minutos suficientes (en 2022 jugó 112 minutos).
- **Primera Nacional** (FBCYL): solo está cargada la temporada 2026.

## Conclusión
1. **En conjunto el método mide bien**: reduce el error y sus intervalos están calibrados (80 % de aciertos del intervalo del 80 %), con 120 a 340 movimientos por par.
2. **En una persona el intervalo es ancho**: ±1 z son unos ±30 puntos de percentil. De los 24 ejes de las tres transiciones, 17 quedaron dentro (71 %), coherente con el 80 % nominal para una muestra tan pequeña. Lo que se sale es sobre todo **papel y posición** (minutos, rebotes, tiros), no nivel.
3. **Lo que E1b debe probar** con el mismo estudio sin fuga: (a) si los **minutos por partido** y el **uso** como covariables estrechan el intervalo, (b) un coeficiente de **conservación por eje** además de la fiabilidad (asistencias y robos se mantienen más que puntos y acierto), (c) la **edad** (una jugadora de 19 a 22 años mejora sola) y (d) la **posición** para los rebotes.
4. La cifra que se enseñaría sigue siendo un **rango y su ancho**, nunca un número: «de media se esperaría un percentil de 55 en Endesa, con el 80 % entre 20 y 85».
