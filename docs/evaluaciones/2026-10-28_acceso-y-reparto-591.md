# Acceso, reparto servidor/paquetes y datos federativos (#591, puerta 0)

Decisión del 28/10/2026 sobre la visión de producto del 26/10 (web multiusuario con niveles; el staff como primer usuario; la app Android como cliente de banda). Sin código. Desbloquea #327 (spike P0 de #326), U5 de #187 y deja #153 condicionada a disparadores concretos.

## Decisiones

| # | Punto | Decisión |
|---|---|---|
| 1 | Niveles y precio | **Se decide después.** Mientras la beta sea gratuita no bloquea nada técnico. Hipótesis de trabajo: libre (tablas, rankings, evolución) y *Club* (scouting, informe de equipo, comparativas, live); unidad natural = club y temporada (`club:<id>` + `temporada:…`), facturable a mano. |
| 2 | Unidad de acceso | **Claves por alcance, sin cuentas.** Se reutiliza el modelo de los paquetes live (#410). #153–#159 quedan aparcadas (ver *Disparadores*). |
| 3 | Reparto de datos | **Destino: todo estático** (evaluado abajo: es viable). **Camino: híbrido** hasta que el spike y las fases P1–P6 de #326 lo confirmen; Render solo se apaga en P7. El predictivo no es bloqueante: su rework profundo está pendiente y puede seguir en servidor o en Actions entretanto. |
| 4 | Datos federativos | **Beta gratuita hasta tener autorización.** No se cobra nada derivado de FEB hasta tener permiso escrito de FEB (y revisar el aviso de FBCYL) o dictamen legal. Se pide en paralelo; no bloquea lo técnico. |
| 5 | Carga del primer usuario | **No hace falta medirla** si el primer usuario se sirve estático (informe y scouting precalculados por equipo y semana). Solo se mide si se mantiene algún cálculo en Render. |

### Puerta legal (punto 4)

El [Aviso Legal de baloncestoenvivo.feb.es](https://baloncestoenvivo.feb.es/avisoLegal.html) atribuye a FEB la titularidad de la propiedad intelectual de la web y prohíbe «la reproducción, la distribución y la comunicación pública de la totalidad o parte de los contenidos […] con fines comerciales» sin autorización, y el uso comercial de las informaciones. **No dice nada específico de estadísticas ni de extracción de bases de datos**: es una zona gris, no un permiso. No es asesoría legal; si «cobrar por el análisis y el software, no por los datos» es defendible es una pregunta para un abogado o para FEB. Pendiente: revisar el aviso de FBCYL y el RGPD/LOPDGDD para datos de jugadores.

Consecuencia técnica: el alcance `abierto` de los paquetes es **comunicación pública** de contenido derivado de FEB (el contenido va en claro). Mientras no haya autorización, la beta se limita al staff y a los clubes invitados con clave, no se abre al público.

## Coste de «todo estático»

### Qué pesan los datos (medido el 28/10/2026 en la BD local)

| Medida | Valor |
|---|---|
| BD local completa | 635 MB en bruto, 63 colecciones (Primera FEB 25/26: 93 MB; 270 partidos) |
| Partido FEB completo | 350 KB bruto → **25 KB comprimido** (PBP 18 KB, box 2,5 KB, tiros 4,9 KB, `DERIVED` 1,2 KB) |
| Partido FBCYL completo | 504 KB bruto → **51 KB comprimido** |
| Partido FEB **sin PBP** (box + tiros + `DERIVED`) | ≈ **8,6 KB** comprimido |
| Temporada de Primera FEB, partidos completos | ≈ 6,8 MB; sin PBP ≈ 2,3 MB |
| Toda la BD local, comprimida | del orden de 45–60 MB (todas las temporadas, con PBP) |

Una competición y temporada cabe holgadamente en el criterio del spike (< ~15 MB); el límite no es el volumen sino qué se calcula y dónde. La razón de que Render (512 MB) no escale es que un partido ocupa ≈ 1 MB en RAM al descomprimirlo.

### Qué hay que reescribir y qué no

El backend tiene ≈ 11,7 k líneas de servicios y ≈ 9,5 k de repositorio y *pipelines* de Mongo (≈ 60 endpoints de lectura). «Estático» **no obliga a reescribirlo todo**: depende de la naturaleza de cada consulta.

| Clase | Ejemplos | Cómo queda en estático | Coste |
|---|---|---|---|
| **A. Lectura por competición** | rankings, estadísticas de equipo y jugador, cuartiles, zonas de tiro, lista de partidos, por periodo, puntos por origen | Vista precalculada por competición y temporada (o filas por partido y agregación local) | **Reescritura** de los *pipelines* a TS o consulta local; es el grueso de P2/P4 y lo que mide el spike |
| **B. Por equipo/jugador, espacio finito** | informe de equipo (propio/rival), scouting del rival, evolución, quintetos, rotaciones, IN/OUT, `together` | Precalculado en Actions por equipo y semana, **con el Python actual** | Bajo: se reutiliza el código; cientos de JSON/PDF pequeños. Punto abierto: la comparación del scouting depende del equipo propio (n² pares) → o se calcula en cliente con dos perfiles precalculados, o se limita |
| **C. Parámetros libres** | comparativas por rango de fechas, históricos entre temporadas | Filas por partido en el dispositivo y cálculo local, carga perezosa por temporada | Medio: reescritura local; ≈ 2,3 MB por temporada sin PBP |
| **D. Modelos** | predicción, Monte Carlo, elasticidades (scikit-learn) | Fuera del camino: en Actions (pares equipo–equipo precalculados) o en servidor hasta el rework del predictivo | Aplazado, no bloquea |
| **E. Administración e ingesta** | scrape, borrado, entrenamiento | Actions y línea de comandos (ya es así en el refresco de Atlas); desaparece la clave de administración de un servidor público | Bajo |
| **F. Exportaciones** | PDF/DOCX, informe semanal ZIP | Los finitos, precalculados con fpdf2/python-docx en Actions; el resto en cliente | Bajo-medio |

### Qué obtiene y qué pierde

- **Obtiene:** sin arranque en frío, sin límite de 512 MB, sin clave de administración pública, coste por usuario ≈ 0, funciona offline y comparte capa de datos con la app. Actions es gratis y sin límite de minutos en repo público; hoy el refresco corre 3 veces al día (05:30, 13:30, 21:30) y `live-packages` tiene un tope de 60 min (≈ 14 s por competición para las jornadas).
- **Pierde / riesgos:**
  1. **Paridad numérica**: cada vista reescrita se revalida contra la API (criterio del spike).
  2. **Rendimiento en el dispositivo** (móvil de gama media): se mide en el spike; si la clase C no cabe, Pyodide con pandas es una opción, con ≈ 10 s de arranque en frío medidos para el motor live.
  3. **Cifrado sin revocación y fuerza bruta offline**: el texto cifrado es público; las claves deben ser largas y aleatorias (las invitaciones lo cubren), nunca contraseñas humanas. Cortar a alguien = rotar el alcance y republicar.
  4. **Alojamiento**: `raw.githubusercontent.com` no tiene SLA y cachea ≈ 5 min; para la web lo razonable es servir los artefactos desde Vercel.
  5. **Más datos en Actions**: el tiempo de precálculo de todas las competiciones senior no está medido; se mide en el spike.

### Veredicto

**Es viable y no hay ninguna funcionalidad que fuerce un servidor**, salvo el predictivo hasta su rework. El coste real es el de la épica #326 (estimación ya hecha: 3–6 meses a tiempo parcial hasta la paridad), concentrado en las clases A y C; las clases B, E y F reutilizan Python en Actions. Por tanto: *todo estático* es el **destino**, no el primer paso; el spike #327 decide el go/no-go con Rankings y Estadísticas de equipo y debe incluir, además de lo previsto, **una pieza de clase B** (informe de equipo precalculado por equipo y cifrado por `club:<id>`), que es lo que el primer usuario necesita, y la medición del tiempo de precálculo de todas las competiciones senior.

## Disparadores para reabrir las cuentas (#153–#159)

Se reabre solo si ocurre alguno: un club pide **revocar a una persona** concreta a mitad de periodo; se necesita **auditar** quién hizo qué; se decide **cobrar por persona**; o aparece una funcionalidad con **datos escritos por el usuario** (notas, planes guardados en servidor).

## Seguimiento

- #327: ampliar el alcance con la pieza de clase B y la medición de precálculo.
- Nuevo issue: solicitar autorización a FEB y revisar el aviso de FBCYL y el RGPD (puerta legal del cobro).
- #153: sigue aparcada con los disparadores de arriba; #326/#187: U5 espera al spike, U0–U4 y U6–U7 ya están hechos.
