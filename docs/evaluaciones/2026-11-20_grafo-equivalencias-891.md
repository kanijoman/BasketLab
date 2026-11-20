# Diseño del grafo de equivalencias entre competiciones (#891, E1)

Parte de la épica #872 (Talent). Diseño corto, con una primera medición sobre lo publicado hoy (`talent-data`, clave abierta de la beta, 89 competiciones, 35.455 filas de jugador-temporada-equipo). **Estado: propuesta, pendiente de las decisiones del final.**

## Para qué sirve
Un percentil de Talent es el del jugador **en su competición**: 80 en LF2 y 80 en Tercera FEB no son lo mismo. E1 da la pieza que falta para compararlos: **qué se esperaría de un jugador si jugara en otra competición**, con su incertidumbre. La usan E4 («puntuación en la competición objetivo», #894), el encaje de #883 entre competiciones (hoy «orientativo» si el jugador es de otra) y, después, E2 y E3.

## Qué hay para estimarlo (medido el 20/11/2026)
Los jugadores que **cambian de competición** son los que enlazan los niveles. Solo cuentan filas con «minutos suficientes» (`eligible`) y personas enlazadas (`linked_to`: nunca por nombre suelto).

| Paso (temporadas consecutivas, ambos lados con minutos) | Jugadores |
|---|---|
| Femenina: LF2 ↔ LF Challenge | 388 (sube) y 95 (baja) |
| Femenina: LF Challenge ↔ LF Endesa | 77 (sube) y 66 (baja) |
| Masculina: Segunda ↔ Primera FEB | 208 y 157 |
| Masculina: Tercera ↔ Segunda FEB | 125 y 102 |
| Masculina: Tercera FEB ↔ Liga U | 99 y 23 |
| Saltos de dos niveles (Primera → Tercera, LF2 → LF Endesa) | 3 y 28: no se estiman, se componen |

De 12.005 personas con minutos, 5.418 aparecen en dos o más competiciones, pero casi todo es la **misma competición en dos temporadas** (los «quedados»): sirven para medir la fiabilidad, no el nivel. Los de formación y las fuentes externas (FBCYL, FIBA) no entran en E1 (ver decisiones).

**Primera señal, sin modelo** (diferencia media del z del percentil entre la temporada anterior y la siguiente; z = inversa de la normal del percentil):

| Paso | Puntos | Asistencias | eFG% |
|---|---|---|---|
| LF2 → LF Challenge (sube) | −0,57 | −0,31 | −0,56 |
| LF Challenge → LF2 (baja) | +0,65 | +0,46 | +0,62 |
| Segunda → Primera FEB | −0,82 | −0,35 | −0,60 |
| Primera → Segunda FEB | +0,92 | +0,44 | +0,57 |
| Tercera → Segunda FEB | −1,08 | −0,34 | −0,79 |
| Segunda → Tercera FEB | +1,17 | +0,33 | +0,98 |

Subir de nivel resta, bajar suma, y casi con la misma magnitud en los dos sentidos: **el nivel de cada competición se puede medir**. Los puntos y el acierto caen más que las asistencias o los rebotes (casi no cambian).

**Fiabilidad de cada estadística** (correlación del z de un jugador entre dos temporadas seguidas en la misma competición, de 400 a 1.600 jugadores por competición): puntos 0,6–0,7, asistencias 0,6–0,8, rebotes ofensivos ~0,75, pérdidas ~0,55 y **eFG% solo 0,34–0,40**. El acierto es muy ruidoso: la traducción tiene que encoger hacia la media (regresión a la media), o diría cosas que no sabe.

## Principios (lo que ScoutingFEB hacía mal)
1. **Sin fuga**: nada de dividir filas al azar; cada temporada se predice con un modelo estimado **sin ella** (walk-forward).
2. **Identidad corroborada**: solo personas enlazadas, ninguna por nombre.
3. **Una escala de niveles, en una dirección** y escrita (la fuente de verdad es `level` del catálogo: 1 = más alto).
4. **Hombres y mujeres, grafos separados** (decidido el 12/11).
5. **Transparente**: una cuenta que se pueda explicar en la ficha; ML solo como contraste.

## Método
**Unidad**: el z del percentil de cada eje del radar (pts, ast, orb, drb, stl, blk, efg, tov), por competición.

**Aristas**: entre competiciones del mismo sexo con **al menos N jugadores que se movieron** (propongo N = 40). Para cada eje *s* y cada paso *A→B*:
`z_B ≈ ρ_s · z_A + δ_AB,s`
- `ρ_s`: la fiabilidad del eje, medida en los quedados (no se supone ni se ajusta con los que se mueven).
- `δ_AB,s`: el cambio de nivel, la media de `z_B − ρ_s · z_A` de los que se movieron en ese paso, **en los dos sentidos a la vez** (A→B con su signo, B→A cambiado de signo: se usan los 480 de LF2↔Challenge y no 388 y 95 por separado).
- Su error típico viene de **remuestrear por persona** (una persona puede aparecer varias temporadas), y se guarda con N.

**Grafo, estimación conjunta y caminos**: las competiciones son nodos y los pasos con N movimientos o más, aristas. En lugar de estimar cada par por separado y componer caminos (que suma errores a ojo), se estima **un valor de nivel por competición y eje** (`θ_c`) con todos los movimientos a la vez, por mínimos cuadrados sobre el grafo (una regresión con un efecto por competición: `z_B − ρ·z_A = θ_B − θ_A + ruido`). Con eso **cualquier par conectado** (también los que nadie ha cruzado) sale como `θ_B − θ_A`, y su incertidumbre sale de la covarianza del ajuste, no de una suma de pasos. Dos competiciones no conectadas no tienen traducción. Es un ajuste pequeño (una incógnita por competición), sin ML.

**Salida**: para un jugador con `z_A` en un eje, el valor esperado en B y un intervalo (la dispersión de lo que el modelo no explica, medida en los mismos movimientos). Sin camino o con intervalo demasiado ancho: **no se da cifra**, se dice «sin datos suficientes».

**Edad**: los que se mueven envejecen un año. E1 usa solo los de 22 años o más (la meseta) y marca el resto; el ajuste fino por edad llega con E2.

## Cómo se comprueba que vale
Una competición-temporada fuera cada vez: se estiman las aristas **sin** esa temporada y se predicen los que se movieron en ella. Se mide:
- el error frente a las dos líneas base (sin traducir: `z_B = z_A`; y solo con la fiabilidad: `ρ · z_A`),
- la **cobertura** de los intervalos (¿el 80 % de los reales cae en el intervalo del 80 %?), que es lo que decide si se puede enseñar una cifra.

Si no mejora a las líneas base o la cobertura se aleja más de 5 puntos del nominal, no se publica la cifra y E4 mantiene «orientativo». Informe y script a mano (como `study:forecast`), no en el CI.

## Qué se publica
`equivalences.json` en `talent-data` (mismo alcance y sellado que lo demás): versión del método, nodos, aristas con `n`, `θ` y su error por eje, la covarianza de los niveles y `ρ` por competición. Determinista (se regenera igual). La cuenta de traducir vive en el navegador (TypeScript con vectores de paridad, como el predictivo): **E4**.

## Troceado en PR
1. **E1a**: tabla de movimientos y de quedados desde las filas publicadas (`src/market/equivalence.py`), con tests sobre filas reales de `tests/local_vectors`.
2. **E1b**: estimador, grafo, composición e incertidumbre, y el estudio walk-forward con su informe.
3. **E1c**: publicación de `equivalences.json` (contrato Python y TypeScript generado).
El puerto a TypeScript y su uso en la ficha son E4.

## Enlazar todas las competiciones entre sí (coste)
No se enlazan «todas las combinaciones»: se estiman **los pasos que alguien ha cruzado** y el resto sale del ajuste conjunto. El coste real no es de cómputo:

| Coste | Estimación |
|---|---|
| **Nodos** (familias de competición, hombres y mujeres por separado) | ~150 si NCAA entra por conferencias (D1 y D2, ~110), FEB y FBCYL ~35, FIBA ~10, ACB 1, Euroliga 2 |
| **Pares posibles** | ~5.600 (2 × 75²/2); los que de verdad tendrán N ≥ 40 movimientos, del orden de 200 a 400 |
| **Cómputo** | despreciable: un sistema de ~150 incógnitas por eje (milisegundos); se publican los `θ` y su covarianza (< 2 MB), no la matriz de pares |
| **Datos** | lo que cuesta es cargar las fuentes (NCAA, Euroliga, ACB ya existe): cada una es su propio bloque; E1 no añade peticiones |
| **Identidad** | **el trabajo grande**: hoy un jugador de una fuente externa se enlaza con una persona de FEB. ACB↔NCAA o Euroliga↔FIBA no pasan por FEB: hace falta un registro de personas **entre fuentes** (componentes conexos de los enlaces, con un id estable, p. ej. el id de FEB si lo hay y, si no, el menor id de fuente). Es un bloque aparte (~2 PR), y cada enlace cruzado se corrobora como ahora (nacimiento y dos palabras del nombre) |
| **Estadística** | los saltos largos tienen intervalos anchos: se publican con su ancho y se limita el camino a 3 saltos; los puentes más fuertes son los que juegan **a la vez** en dos competiciones (Euroliga y ACB con el mismo club; las selecciones de FIBA y la liga de su país), no solo los que cambian de temporada |
| **Riesgo** | un enlace falso entre fuentes mueve el nivel de una competición entera: la regla es la conservadora (corroboración doble, y ante la duda no se enlaza: pierde movimientos, no sesga) |

**Orden razonable**: E1 con las competiciones de FEB ya cargadas (E1a a E1c); el registro de personas entre fuentes cuando haya dos fuentes externas con datos (ACB y NCAA o Euroliga); y cada fuente nueva añade sus nodos sin cambiar el método.

## Decisiones que necesito
1. **Estadísticas**: los 8 ejes del radar (recomendado) o también uso y ritmo.
2. **Mínimo de movimientos por arista**: N = 40 (recomendado); con menos, esa arista no existe y se compone por otra.
3. **Formación**: la formación (U12 a U18) a sénior queda **fuera** de E1 y dentro de E3 (su pregunta es otra: potencial, no nivel de liga). Recomendado.
4. **Fuentes externas**: FBCYL y FIBA se unen cuando haya jugadores enlazados en dos competiciones; ACB, NCAA y la Euroliga se añaden como nodos cuando estén cargadas, sin cambiar el método. Recomendado.
5. **Cifra o rango**: la ficha enseña siempre un **rango** y nunca una cifra sola (la regla de la proyección «¿Y si…?» del predictivo). Recomendado.
