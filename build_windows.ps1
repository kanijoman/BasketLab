# Build script for Windows - MetricsForAll
# Run this script to test the build locally before creating a release

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MetricsForAll - Windows Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
Write-Host "Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version
    Write-Host "✓ $pythonVersion found" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found. Please install Python 3.8+ first." -ForegroundColor Red
    exit 1
}

# Check if in correct directory
if (-not (Test-Path "MetricsForAll.spec")) {
    Write-Host "✗ Error: MetricsForAll.spec not found." -ForegroundColor Red
    Write-Host "  Please run this script from the project root directory." -ForegroundColor Red
    exit 1
}

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install -r requirements.txt

# Check if PyInstaller is installed
Write-Host ""
Write-Host "Checking PyInstaller..." -ForegroundColor Yellow
try {
    pip show pyinstaller | Out-Null
    Write-Host "✓ PyInstaller is installed" -ForegroundColor Green
} catch {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
}

# Clean previous builds
Write-Host ""
Write-Host "Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
    Write-Host "✓ Removed build/ directory" -ForegroundColor Green
}
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
    Write-Host "✓ Removed dist/ directory" -ForegroundColor Green
}

# Build with PyInstaller
Write-Host ""
Write-Host "Building executable with PyInstaller..." -ForegroundColor Yellow
Write-Host "This may take several minutes..." -ForegroundColor Gray
pyinstaller MetricsForAll.spec

# Check if build was successful
if (Test-Path "dist\MetricsForAll\MetricsForAll.exe") {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  ✓ Build completed successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Executable location: dist\MetricsForAll\MetricsForAll.exe" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To test the executable:" -ForegroundColor Yellow
    Write-Host "  cd dist\MetricsForAll" -ForegroundColor Gray
    Write-Host "  .\MetricsForAll.exe" -ForegroundColor Gray
    Write-Host ""
    Write-Host "To create a distribution archive:" -ForegroundColor Yellow
    Write-Host "  Compress-Archive -Path dist\MetricsForAll\* -DestinationPath MetricsForAll-Windows.zip" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "✗ Build failed. Check the output above for errors." -ForegroundColor Red
    exit 1
}
