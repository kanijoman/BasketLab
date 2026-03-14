# Script de instalación de dependencias para BasketLab
# Incluye la nueva librería python-docx para generación de informes DOCX

Write-Host "Instalando dependencias de BasketLab..." -ForegroundColor Green
Write-Host ""

# Actualizar pip
Write-Host "Actualizando pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

Write-Host ""
Write-Host "Instalando librerías necesarias..." -ForegroundColor Yellow
Write-Host ""

# Instalar dependencias desde requirements.txt
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt
} else {
    Write-Host "Archivo requirements.txt no encontrado. Instalando dependencias manualmente..." -ForegroundColor Red

    # GUI Framework
    pip install PyQt6

    # Database
    pip install pymongo

    # Data Analysis & Visualization
    pip install matplotlib numpy scipy pandas

    # PDF & Document Generation
    pip install fpdf2 python-docx

    # Web Scraping
    pip install requests beautifulsoup4

    # Other utilities
    pip install Pillow
}

Write-Host ""
Write-Host "¡Instalación completada!" -ForegroundColor Green
Write-Host ""
Write-Host "Nuevas funcionalidades disponibles:" -ForegroundColor Cyan
Write-Host "- Generación de informes de scouting en formato DOCX" -ForegroundColor White
Write-Host "  Acceso: Estadísticas Individuales > Exportar > Informe de Scouting (DOCX)" -ForegroundColor White
Write-Host ""
Write-Host "Para más información, consulte INFORME_SCOUTING_README.md" -ForegroundColor Yellow
