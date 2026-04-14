"""SystemTray — QSystemTrayIcon para o BOLECODE desktop."""

from __future__ import annotations

from PySide6.QtCore import Signal, QObject
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu


def _make_icon(color: str = "#2563eb", letter: str = "B") -> QIcon:
    """Gera icone 64x64 com QPainter (sem Pillow)."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Fundo arredondado
    painter.setBrush(QColor(color))
    painter.setPen(QColor(0, 0, 0, 0))
    painter.drawRoundedRect(0, 0, 64, 64, 12, 12)

    # Letra
    painter.setPen(QColor("white"))
    font = QFont("Arial", 30, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), 0x0084, letter)  # AlignCenter

    painter.end()
    return QIcon(pixmap)


class SystemTray(QObject):
    """QSystemTrayIcon com menu e notificacoes nativas."""

    show_requested = Signal()
    quit_requested = Signal()
    pause_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paused = False

        self._tray = QSystemTrayIcon(parent)
        self._tray.setIcon(_make_icon("#2563eb", "B"))
        self._tray.setToolTip("BOLECODE — Monitor de Cobranca")

        # Menu
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: #1a1e2e;
                border: 1px solid #252a3a;
                color: #e2e8f0;
                padding: 4px;
            }
            QMenu::item:selected {
                background: #2563eb;
            }
        """)

        self._act_show = QAction("Mostrar", menu)
        self._act_show.triggered.connect(self.show_requested.emit)
        menu.addAction(self._act_show)

        menu.addSeparator()

        self._act_pause = QAction("Pausar Servico", menu)
        self._act_pause.triggered.connect(self._toggle_pause)
        menu.addAction(self._act_pause)

        menu.addSeparator()

        act_quit = QAction("Sair", menu)
        act_quit.triggered.connect(self.quit_requested.emit)
        menu.addAction(act_quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_requested.emit()

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._paused:
            self._act_pause.setText("Retomar Servico")
            self._tray.setIcon(_make_icon("#eab308", "\u2016"))
            self._tray.setToolTip("BOLECODE — Pausado")
        else:
            self._act_pause.setText("Pausar Servico")
            self._tray.setIcon(_make_icon("#2563eb", "B"))
            self._tray.setToolTip("BOLECODE — Ativo")
        self.pause_toggled.emit(self._paused)

    def update_status(self, ok: bool) -> None:
        """Atualiza cor do icone: verde=ok, vermelho=erro."""
        if self._paused:
            return
        color = "#22c55e" if ok else "#ef4444"
        self._tray.setIcon(_make_icon(color, "B"))

    def notify(self, title: str, message: str,
               icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
               duration_ms: int = 5000) -> None:
        """Exibe toast notification nativa do Windows."""
        self._tray.showMessage(title, message, icon, duration_ms)
