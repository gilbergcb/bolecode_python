@echo off
REM BOLECODE — Inicializacao rapida (desenvolvimento)
cd /d "%~dp0"
call .venv\Scripts\activate.bat 2>nul || (
    echo Venv nao encontrado. Execute setup.bat primeiro.
    pause & exit /b 1
)
echo Iniciando BOLECODE...
python main.py
