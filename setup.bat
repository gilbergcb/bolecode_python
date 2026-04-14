@echo off
REM ============================================================
REM  BOLECODE — Setup para Windows 10+ / Windows Server 2016+
REM  Execute como Administrador
REM ============================================================

setlocal EnableDelayedExpansion

echo.
echo  ============================================
echo   BOLECODE — Instalacao automatica
echo  ============================================
echo.

REM Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale Python 3.11+ e adicione ao PATH.
    pause & exit /b 1
)

REM Verifica pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] pip nao encontrado.
    pause & exit /b 1
)

REM Cria venv se nao existe
if not exist ".venv" (
    echo [1/5] Criando ambiente virtual...
    python -m venv .venv
)

REM Ativa venv
call .venv\Scripts\activate.bat

REM Instala dependencias
echo [2/5] Instalando dependencias...
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    pause & exit /b 1
)

REM Copia .env.example se .env nao existe
if not exist ".env" (
    echo [3/5] Criando .env a partir do exemplo...
    copy .env.example .env
    echo.
    echo  IMPORTANTE: Edite o arquivo .env com suas configuracoes antes de continuar!
    echo  Abrindo .env no Notepad...
    notepad .env
) else (
    echo [3/5] .env ja existe. Pulando.
)

REM Cria pastas necessarias
echo [4/5] Criando estrutura de diretorios...
if not exist "logs"  mkdir logs
if not exist "certs" mkdir certs

echo [5/5] Instalacao concluida!
echo.
echo  ============================================
echo   Como executar:
echo.
echo   Desenvolvimento (terminal):
echo     .venv\Scripts\activate
echo     python main.py
echo.
echo   Servico Windows (como Administrador):
echo     .venv\Scripts\python install_service.py install
echo     .venv\Scripts\python install_service.py start
echo  ============================================
echo.
pause
