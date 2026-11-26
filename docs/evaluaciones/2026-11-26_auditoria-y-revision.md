# Auditoría externa y revisión del código (26/11/2026)

Origen: una auditoría externa (previa y simulación, Live, Talent, mercado y almacenamiento en GitHub) y una revisión propia en cinco ejes (rendimiento, alineamiento entre productos, procesos complejos, DRY/SOLID y tests), contrastadas con el código, los issues y los workflows reales.

## Resultado de contrastar la auditoría
- La dirección coincide con la nuestra. De sus tres prioridades, dos ya estaban resueltas o descartadas: las equivalencias en el encaje de Talent (E4c, #1047) y el feedback por alerta (#235 → #314 → #933).
- Su primera mejora de datos (caché de Talent) apunta al sitio equivocado: `talent-data` tarda 4 min y `web-data` 32-41 min, de los cuales la sección `reports` ocupa 1.971 s de 2.119 (93 %) y se recalcula siempre.

## Medidas (26/11/2026)
Ramas publicadas: web-data 183 MB / 10.883 ficheros, web-data-ext 189 MB, talent-data 17 MB, live-packages 10 MB. Manifiesto de web-data 3,1 MB; índice NCAA ACC 3,6 MB con 167 equipos para 18 miembros. CI: lotes backend 236/325/321/377 s; `live-android` en PR 12 min.

## Decisiones del usuario
Todo en épicas y por fases; primero los bugs, después #1102; desempates del Anexo D de FIBA; sin medición del feedback en Live; ratings con posesiones reales (el escalado a 40 min solo para el ritmo); fórmulas de CLAUDE.md en todas las páginas con un registro único; zonas de tiro con cuartiles en web, Talent y PDF.

## Backlog
Épicas #1108 (bugs), #1109 (publicaciones), #1110 (CI), #1111 (fórmulas y alineamiento), #1112 (tests), #1113 (DRY/SOLID), #1114 (predictivo), #1115 (Live), más sub-issues en #1102 y #872.

## Bugs resueltos en el primer bloque (E1)
- #1121 dos líneas con el mismo número: gana la última. #1120 línea desaparecida: reconstrucción; documento más antiguo: se ignora.
- #1118 técnica dentro de una serie de TL (un TL técnico y la serie conserva su posesión). Efecto colateral medido en 6 partidos reales: 5 mejoran (2524461 pasa de «dudoso» a «ok») y 2524468 pasa de 2 a 3 roturas (flagrante sobre una canasta con tiro adicional); «Flagrante» pasa a contar como antideportiva.
- #1122 probabilidad de victoria en prórroga. #1119 (parcial) el reloj ya no retrocede por una línea tardía.
- Sin resolver en este bloque: #1123 (el cuadre por métrica es una decisión de #351 y falta el partido 2536129 para reproducirlo), #1124, la segunda parte de #1119 (orden por número en live y por reloj en DERIVED) y los tests de propiedades I1/I2.
