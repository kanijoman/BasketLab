# 🚀 Guía de Distribución de Ejecutables

> ⚠️ **Nota**: Esta guía describe el proceso de distribución del **cliente de escritorio (deprecado)**. BasketLab está migrando a una aplicación web; la documentación de despliegue web se añadirá próximamente.

Esta guía explica cómo crear releases con ejecutables automáticos para Windows y macOS.

## 📦 Sistema de Build Automático

Este proyecto usa **GitHub Actions** para compilar automáticamente ejecutables cuando creas un release.

## ✨ Crear un Release (Recomendado)

### Opción 1: Desde la Interfaz Web de GitHub

1. Ve a tu repositorio en GitHub
2. Click en **"Releases"** en la barra lateral derecha
3. Click en **"Create a new release"** o **"Draft a new release"**
4. En **"Choose a tag"**, escribe un nuevo tag (ej: `v1.0.0`, `v1.1.0`)
5. Click en **"Create new tag: v1.0.0 on publish"**
6. Escribe un título para el release (ej: "BasketLab v1.0.0")
7. Agrega notas del release (opcional pero recomendado)
8. Click en **"Publish release"**

### Opción 2: Desde Git (Línea de Comandos)

```bash
# Asegúrate de que tus cambios están commiteados
git add .
git commit -m "Release v1.0.0"

# Crear y pushear el tag
git tag v1.0.0
git push origin v1.0.0

# Luego ve a GitHub y crea el release desde el tag
```

## ⚙️ ¿Qué Sucede Automáticamente?

Cuando publicas un release:

1. **GitHub Actions detecta el nuevo tag**
2. **Compila en Windows**:
   - Instala Python 3.11
   - Instala dependencias
   - Ejecuta PyInstaller
   - Crea `BasketLab-Windows.zip`
3. **Compila en macOS**:
   - Instala Python 3.11
   - Instala dependencias
   - Ejecuta PyInstaller
   - Crea `BasketLab-macOS.dmg`
4. **Sube los ejecutables al release automáticamente**

**Tiempo estimado**: 10-15 minutos

## 🔍 Monitorear el Build

1. Ve a la pestaña **"Actions"** en GitHub
2. Verás el workflow "Build Executables" corriendo
3. Click para ver el progreso en tiempo real
4. Si hay errores, aparecerán en los logs

## 🧪 Probar Localmente (Antes del Release)

### Windows

```powershell
# Ejecutar script de build
.\build_windows.ps1

# El ejecutable estará en:
# dist\BasketLab\BasketLab.exe

# Probar
cd dist\BasketLab
.\BasketLab.exe
```

### macOS

```bash
# Instalar dependencias
pip install -r requirements.txt
pip install pyinstaller

# Compilar
pyinstaller BasketLab.spec

# Probar
open dist/BasketLab.app
```

## 📋 Checklist Pre-Release

Antes de crear un release, asegúrate de:

- [ ] Todos los cambios están commiteados
- [ ] Has probado la aplicación localmente
- [ ] Has actualizado el README si hay nuevas funcionalidades
- [ ] Has decidido el número de versión (sigue [Semantic Versioning](https://semver.org/))
  - `v1.0.0` - Release mayor con cambios significativos
  - `v1.1.0` - Nuevas funcionalidades (minor)
  - `v1.0.1` - Corrección de bugs (patch)
- [ ] Has probado el build local (opcional pero recomendado)

## 🐛 Solución de Problemas

### El workflow falla

1. Ve a la pestaña **Actions** en GitHub
2. Click en el workflow fallido
3. Revisa los logs para ver el error
4. Errores comunes:
   - **Dependencia faltante**: Agregar a `requirements.txt`
   - **Archivo no encontrado**: Verificar rutas en `BasketLab.spec`
   - **Importación fallida**: Agregar módulo a `hiddenimports` en spec

### El ejecutable no inicia

1. Verificar que MongoDB esté instalado y corriendo
2. En Windows: Ejecutar desde CMD/PowerShell para ver mensajes de error
3. En macOS: Abrir desde Terminal: `open dist/BasketLab.app`
4. Revisar logs en:
   - Windows: `%TEMP%\BasketLab\`
   - macOS: `~/Library/Logs/BasketLab/`

## 📝 Notas Importantes

- **Repositorios públicos**: Builds ilimitados y gratuitos ✅
- **Repositorios privados**: 2,000 minutos/mes gratis (consulta uso en Settings > Billing)
- **Tamaño del ejecutable**: ~150-200 MB (incluye Python + todas las dependencias)
- **Primera ejecución**: Puede tardar unos segundos en iniciar
- **Actualizaciones**: Los usuarios deben descargar el nuevo ejecutable manualmente

## 🔗 Enlaces Útiles

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [PyInstaller Documentation](https://pyinstaller.org/)
- [Semantic Versioning](https://semver.org/)

## 💡 Tips

- Crea releases para versiones estables, no para cada commit
- Usa tags descriptivos: `v1.0.0`, `v1.1.0-beta`, etc.
- Incluye notas de release con cambios importantes
- Agrega instrucciones de instalación en las notas del release
