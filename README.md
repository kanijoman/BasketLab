# MetricsForAll
Metrics for all es una aplicación para análisis estadístico avanzado de baloncesto usando información proporcionada por la FEB y distintas federaciones regionales en España. La funcionalidad básica es un scraper de datos de la fuente de datos donde están alojadas las competiciones (actualmente, sólo la FEB), para recuperar información estructurada y almacenarla en una base de datos en el cloud (MongoDB orientada a JSON).

Actualmente está en una primera fase de prueba de concepto con la competición de Liga Femenina 2 (LF2) de la FEB. Potencialmente se irán añadiendo más competiciones de la FEB y de otras federaciones autonómicas.

Añadir nuevas federaciones resulta un cambio complejo que se abordará en fases posteriores debido a que la estructura de la información difiere de la FEB y, por tanto, habría que aplicar una transformación a estos datos de origen para poder usar los mismos métodos de análsis.
Las funcionalidades actuales incluyen:
  * Ventana usando PyQt6 para selección de competición, temporada y grupo:
    *  Pendiente de evaluar otros pontenciales GUI.
    *  Pendiente de mejorar la UI, ahora estrictamente básica y funcional.
    *  Pendiente añadir nueva funcionalidad para generación de informes
  * Pendiente de evaluar competiciones distintas a LF2, potencialmente se podría trabajar con cualquier competición FEB.
   * Aunque ahora aparece Primera Nacional, no es funcional, sólo a modo de placeholder para evaluar el combo box
  * Pendiente de añadir nuevas competiciones de federaciones regionales.
  * Pendiente de revisar posibles transformaciones de datos en los JSON originales (normalización de datos)
  * Pendiente de realizar consultas a MongoDB para recuperar la información estructurada
  * Pendiente de realizar el análisis estadístico:
    * Gráficos de estadística avanzada por equipo: General, local, visitante, último mes, etc.
    * Gráficos de estadística avanzada por jugador: mismo que para equipo
    * Perfil de lanzamiento de jugador: mapa de calor y lanzamientos por zonas
    * Perfil de juego: gráfico radial con características de juego
    * Otros: quintetos, on/off, parejas, tríos, etc...
  * Pendiente dejar enlaces de descarga a ejecutables stand-alone para ejecutar desde ordenadores sin entorno python
