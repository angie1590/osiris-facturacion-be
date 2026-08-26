@echo off
REM Script de validación para Windows
REM Uso: validate.bat

echo.
echo ============================================================
echo    VALIDACION DE CONFIGURACION OSIRIS-BE (Windows)
echo ============================================================
echo.

REM Intentar con python (común en Windows)
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python scripts\validate_setup.py
    exit /b %ERRORLEVEL%
)

REM Si no existe python, intentar con python3
where python3 >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python3 scripts\validate_setup.py
    exit /b %ERRORLEVEL%
)

REM No se encontró Python
echo ERROR: Python no esta instalado o no esta en el PATH
echo.
echo Instala Python desde: https://www.python.org/downloads/
echo Asegurate de marcar "Add Python to PATH" durante la instalacion
echo.
exit /b 1
