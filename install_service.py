"""
install_service.py — Instala/Remove BOLECODE como serviço Windows.

Requer:
  - pywin32 instalado
  - Executar como Administrador

Uso:
  python install_service.py install   # instala e configura auto-start
  python install_service.py start     # inicia o serviço
  python install_service.py stop      # para o serviço
  python install_service.py remove    # remove o serviço
  python install_service.py status    # exibe status
"""
from __future__ import annotations

import sys
import os
import subprocess
from pathlib import Path

SERVICE_NAME = "BOLECODE"
SERVICE_DISPLAY = "BOLECODE — Monitor de Cobrança Bradesco"
SERVICE_DESC = "Sincroniza Winthor/Oracle com a API Bradesco e registra boletos híbridos com QR Code."

PROJECT_DIR = Path(__file__).parent.resolve()
PYTHON_EXE = Path(sys.executable)
MAIN_SCRIPT = PROJECT_DIR / "main.py"


def _run(cmd: list[str]) -> int:
    return subprocess.call(cmd)


def _sc(args: list[str]) -> int:
    return _run(["sc"] + args)


def install():
    print(f"Instalando serviço '{SERVICE_NAME}'...")
    # Cria serviço usando sc.exe (nativo Windows)
    binpath = f'"{PYTHON_EXE}" "{MAIN_SCRIPT}"'
    ret = _sc([
        "create", SERVICE_NAME,
        f"binPath= {binpath}",
        "start= auto",
        f"DisplayName= {SERVICE_DISPLAY}",
    ])
    if ret != 0:
        print("ERRO ao criar serviço. Execute como Administrador.")
        return

    # Adiciona descrição
    _sc(["description", SERVICE_NAME, SERVICE_DESC])

    # Configura diretório de trabalho via registry
    try:
        import winreg
        key_path = rf"SYSTEM\CurrentControlSet\Services\{SERVICE_NAME}"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "Environment", 0, winreg.REG_MULTI_SZ,
                          [f"BOLECODE_DIR={PROJECT_DIR}"])
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Aviso: não foi possível definir diretório de trabalho: {e}")

    print(f"Serviço instalado. Use: python install_service.py start")


def start():
    print(f"Iniciando serviço '{SERVICE_NAME}'...")
    _sc(["start", SERVICE_NAME])


def stop():
    print(f"Parando serviço '{SERVICE_NAME}'...")
    _sc(["stop", SERVICE_NAME])


def remove():
    stop()
    import time; time.sleep(2)
    print(f"Removendo serviço '{SERVICE_NAME}'...")
    _sc(["delete", SERVICE_NAME])


def status():
    _sc(["query", SERVICE_NAME])


COMMANDS = {
    "install": install,
    "start": start,
    "stop": stop,
    "remove": remove,
    "status": status,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Uso: python install_service.py [{' | '.join(COMMANDS)}]")
        sys.exit(1)
    COMMANDS[sys.argv[1]]()
