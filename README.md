# MetricsForAll

Aplicación de análisis de baloncesto para análisis estadístico avanzado utilizando datos de la Federación Española de Baloncesto (FEB) y federaciones regionales.

## Descripción General

MetricsForAll es una aplicación para el análisis estadístico avanzado de baloncesto utilizando información proporcionada por la FEB (Federación Española de Baloncesto) y varias federaciones regionales en España. La funcionalidad básica incluye:

- **Scraper de datos** desde fuentes configuradas donde se alojan las competiciones (actualmente solo FEB)
- **Recuperación de información estructurada** y almacenamiento en una base de datos en la nube (MongoDB, orientada a JSON)
- **Herramientas de análisis estadístico** para métricas básicas y avanzadas

Actualmente en la primera fase de prueba de concepto con la competición LF2 (Liga Femenina 2) de la FEB. Se añadirán más competiciones de la FEB y otras federaciones regionales en el futuro.

## Características

### Recopilación de Datos
- **Scraper Inteligente**: Recopilación automática de datos desde la FEB
- **Almacenamiento en MongoDB**: Base de datos en la nube con estructura JSON
- **Actualizaciones Automáticas**: Sistema de sincronización para mantener información actualizada
- **Gestión de Tokens**: Control de acceso y rate limiting para API de la FEB

### Interfaz de Usuario (PyQt6)
- **Selector de Competición**: Elección de competición, temporada y grupo
- **Actualización Dinámica**: Botón "Actualizar y Ver Estadísticas" que:
  - Sincroniza datos con la fuente (FEB)
  - Calcula métricas básicas y avanzadas
  - Genera estadísticas de equipos y rivales
- **Ventanas Especializadas**:
  - Estadísticas por Equipos (básicas y avanzadas)
  - Análisis de Rivales
  - Shot Charts y mapas de calor
  - Zonas de rendimiento por área de cancha

### Ventana de Estadísticas

#### Características Principales
- **Análisis de Equipos y Rivales**: Visualización de estadísticas propias y de los oponentes con pestañas separadas
- **Métricas Avanzadas**: Cálculo ajustado de posesiones considerando prórrogas, con normalización a partidos de 40 minutos
- **Filtrado Temporal**: Selector de período con dos modos:
  - **General**: Estadísticas de toda la temporada
  - **Comparativa Mensual**: Análisis del último mes vs resto de temporada con indicadores de tendencia

#### Indicadores de Tendencia (Modo Comparativo)
- **⇈** Mejora significativa (>10%) - Verde oscuro
- **↑** Mejora moderada (5-10%) - Verde claro
- **≈** Sin cambios (<5%) - Gris
- **↓** Empeoramiento moderado (5-10%) - Naranja
- **⇊** Empeoramiento significativo (>10%) - Rojo

#### Visualización
- Información codificada por colores según cuartiles:
  - Q1: Verde (mejor rendimiento)
  - Q2: Amarillo
  - Q3: Naranja
  - Q4: Rojo (peor rendimiento)
- Agrupación visual de métricas por categorías (Rendimiento, Eficiencia, Defensa, Rebotes, etc.)
- Ordenable por cualquier columna (ascendente/descendente)
- Ajuste automático de tamaño de ventana según contenido

#### Exportación de Datos
- **CSV**: Exportación con separación por punto y coma
- **PNG**: Captura de imagen de alta calidad
- **PDF**: Documento en formato horizontal para mejor visualización

## Visualización de Cancha FIBA

Este proyecto incluye un módulo **Generador de Cancha de Baloncesto FIBA** para crear visualizaciones de media cancha con dimensiones oficiales FIBA.

### Inicio Rápido

```python
from src.shotcharts import plot_court_with_theme
import matplotlib.pyplot as plt

# Generar una media cancha FIBA con fondo blanco
fig = plot_court_with_theme(theme='light', title='Media Cancha FIBA')
plt.show()
```

### Características
- Dimensiones oficiales de cancha FIBA (todas en metros)
- Elementos completos de la cancha (zona, línea de tres puntos, área restringida, etc.)
- Temas de color predefinidos (light, wood, dark, classic, modern)
- Colores y tamaños personalizables
- Exportación a múltiples formatos (PNG, PDF, SVG)
- Soporte para superposición de datos en gráficos de tiros y mapas de calor
- Fondo blanco por defecto para visualizaciones limpias

### Documentación

Para documentación detallada sobre el generador de cancha FIBA, consulte:
- [`src/shotcharts/README.md`](src/shotcharts/README.md) - Referencia completa de la API y guía de uso
- [`src/shotcharts/example_usage.py`](src/shotcharts/example_usage.py) - Ejemplos simples de uso

### Ejemplo

```python
from src.shotcharts import FIBACourt
import matplotlib.pyplot as plt

# Crear cancha y agregar datos de tiros
court = FIBACourt()
fig = court.plot_court(title='Gráfico de Tiros')
ax = fig.axes[0]

# Agregar tiros
ax.scatter([7.5, 8.2], [3.5, 5.2], c='green', s=100, label='Anotado')
ax.scatter([6.8], [7.1], c='red', s=100, marker='x', label='Fallado')
ax.legend()

plt.show()
```

## Análisis de Zonas de Rendimiento

El sistema incluye un **Análisis de Rendimiento por Zonas** que divide la cancha FIBA en 10 zonas tácticas detalladas y calcula estadísticas de tiro para cada zona.

### Características
- **10 zonas detalladas**: División táctica basada en distancia y posición
  - 2 zonas interiores (área restringida, zona)
  - 3 zonas de tiro medio (corto, medio, largo - basadas en distancia)
  - 5 zonas de tres puntos (esquinas, alas, centro - divididas en puntos de quiebre)
- **Visualización con gradiente de color**: Paleta suave de 8 colores (rojo → amarillo → verde)
- **Umbrales realistas de baloncesto**:
  - 2 puntos: Pobre <30%, Promedio 30-40%, Excelente >40%
  - 3 puntos: Pobre <20%, Promedio 20-30%, Excelente >30%
- **Integración con UI**: Disponible como opción "Zonas de Rendimiento" en la ventana de Shot Charts

### Uso en la UI
1. Abrir **Shot Charts** desde el menú principal
2. Seleccionar un equipo
3. Elegir filtro (opcional): Todos / Aciertos / Fallos
4. Seleccionar **"Zonas de Rendimiento"** como tipo de visualización
5. Ver análisis con zonas codificadas por colores y estadísticas

### Uso Programático

```python
from src.shotcharts import ZoneAnalyzer

# Inicializar analizador
analyzer = ZoneAnalyzer(detail_level='detailed')

# Cargar y analizar tiros
shots = analyzer.load_feb_game_data('path/to/game.json')
stats = analyzer.analyze_zone_performance(shots)

# Crear visualización
fig = analyzer.plot_zone_analysis(stats, title='Análisis de Zonas del Equipo')
plt.show()
```

## Arquitectura Técnica

### Base de Datos (MongoDB)
- **Agregación Avanzada**: Pipelines optimizados para cálculo de métricas
- **Filtrado Temporal**: Consultas con `$addFields` y `$dateFromString` para análisis por períodos
- **Esquema Flexible**: Soporte para estructura JSON de múltiples fuentes

### Cálculos Estadísticos
- **Posesiones Ajustadas**: Normalización a 40 minutos para partidos con prórroga
  - Fórmula: `possessions × (40 / minutos_totales)`
  - Minutos totales: `(num_cuartos - 4) × 5 + 40`
- **Métricas Avanzadas**: Efficiency Rating, True Shooting, Assist Rate, etc.
- **Análisis Comparativo**: Cálculo de deltas porcentuales entre períodos

### Interfaz Gráfica (PyQt6)
- **Widgets Personalizados**: Items de tabla con ordenamiento numérico
- **Renderizado HTML**: QLabel para indicadores de tendencia con colores
- **Diseño Responsivo**: Ajuste automático de tamaño de ventana
- **Callbacks**: Sistema de recarga dinámica con filtros temporales

## Desarrollo Futuro

- Agregar más competiciones de la FEB (Liga Femenina, LEB Oro, LEB Plata)
- Integración con federaciones regionales (estructura de datos diferente)
- Análisis predictivo con Machine Learning
- Exportación a formatos adicionales (Excel, JSON)
- Comparativas entre equipos y temporadas
- Dashboard interactivo con gráficos temporales

## Instalación

```bash
# Instalar paquetes requeridos
pip install numpy matplotlib pymongo PyQt6
```

## Uso

Ejecutar la aplicación principal:
```bash
python src/main.py
```

Generar visualizaciones de cancha FIBA:
```bash
python -m src.shotcharts.fiba_court
# o
python -m src.shotcharts.example_usage
```
