"""
ui/tray.py — Ícone na bandeja do sistema (Windows 10/11/Server 2016+).

Usa pystray + Pillow para desenhar o ícone dinamicamente.
Menu permite: Abrir Dashboard, Pausar/Retomar, Sair.
"""
from __future__ import annotations

import threading
import webbrowser
from io import BytesIO
from typing import Callable

from PIL import Image, ImageDraw, ImageFont
from loguru import logger

try:
    import pystray
    TRAY_AVAILABLE = True
except Exception:
    TRAY_AVAILABLE = False


def _make_icon(color: str = "#2563eb", letter: str = "B") -> Image.Image:
    """Gera ícone 64×64 com letra centrada."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Fundo arredondado
    draw.rounded_rectangle([0, 0, 63, 63], radius=12, fill=color)
    # Letra
    try:
        font = ImageFont.truetype("arialbd.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), letter, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((64 - w) / 2 - bbox[0], (64 - h) / 2 - bbox[1]), letter, fill="white", font=font)
    return img


class TrayApp:
    def __init__(
        self,
        dashboard_url: str,
        on_pause: Callable | None = None,
        on_resume: Callable | None = None,
        on_quit: Callable | None = None,
    ):
        self.dashboard_url = dashboard_url
        self.on_pause = on_pause
        self.on_resume = on_resume
        self.on_quit = on_quit
        self._paused = False
        self._icon: pystray.Icon | None = None

    def _open_dashboard(self, icon, item):
        webbrowser.open(self.dashboard_url)

    def _toggle_pause(self, icon, item):
        self._paused = not self._paused
        if self._paused:
            logger.info("Serviço pausado pelo usuário.")
            if self.on_pause:
                self.on_pause()
            self._icon.icon = _make_icon("#eab308", "‖")
            self._icon.title = "BOLECODE — Pausado"
        else:
            logger.info("Serviço retomado pelo usuário.")
            if self.on_resume:
                self.on_resume()
            self._icon.icon = _make_icon("#2563eb", "B")
            self._icon.title = "BOLECODE — Ativo"

    def _quit(self, icon, item):
        logger.info("Encerrando via tray...")
        if self.on_quit:
            self.on_quit()
        icon.stop()

    def update_status(self, ok: bool) -> None:
        """Atualiza cor do ícone conforme status do serviço."""
        if self._icon:
            color = "#22c55e" if ok else "#ef4444"
            self._icon.icon = _make_icon(color, "B")

    def run(self) -> None:
        if not TRAY_AVAILABLE:
            logger.warning("pystray não disponível — sem tray icon.")
            return

        icon_img = _make_icon("#2563eb", "B")

        menu = pystray.Menu(
            pystray.MenuItem("Abrir Dashboard", self._open_dashboard, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: "Retomar Serviço" if self._paused else "Pausar Serviço",
                self._toggle_pause,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", self._quit),
        )

        self._icon = pystray.Icon(
            "BOLECODE",
            icon_img,
            "BOLECODE — Monitor de Cobrança",
            menu=menu,
        )

        # Duplo-clique abre dashboard (Windows)
        self._icon.run()

    def run_detached(self) -> threading.Thread:
        """Inicia tray em thread separada. Retorna a thread."""
        t = threading.Thread(target=self.run, daemon=True, name="tray")
        t.start()
        return t
