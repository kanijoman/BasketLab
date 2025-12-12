# MetricsForAll - Configuración de Base de Datos

Este archivo contiene instrucciones para desarrolladores sobre la configuración de la base de datos.

## Para Usuarios Finales

No necesitas configurar nada. La aplicación viene pre-configurada con acceso a la base de datos.

## Para Desarrolladores

### Configuración Local

Para desarrollo, crea el archivo `src/database/db_credentials.txt` con la cadena de conexión de MongoDB:

```
mongodb+srv://usuario:contraseña@cluster.mongodb.net/
```

**IMPORTANTE:** Este archivo NO debe subirse al repositorio Git (ya está en .gitignore).

### Variables de Entorno (Opcional)

También puedes usar una variable de entorno:

```bash
# Windows PowerShell
$env:MONGODB_CONNECTION_STRING="mongodb+srv://usuario:contraseña@cluster.mongodb.net/"

# Windows CMD
set MONGODB_CONNECTION_STRING=mongodb+srv://usuario:contraseña@cluster.mongodb.net/

# Linux/macOS
export MONGODB_CONNECTION_STRING="mongodb+srv://usuario:contraseña@cluster.mongodb.net/"
```

### Construcción del Ejecutable

El archivo `db_credentials.txt` se incluye automáticamente en el ejecutable durante el proceso de build con PyInstaller (ver `MetricsForAll.spec`).

### Prioridad de Configuración

1. Variable de entorno `MONGODB_CONNECTION_STRING`
2. Archivo `src/database/db_credentials.txt`
3. Configuración por defecto (en distribución compilada)
