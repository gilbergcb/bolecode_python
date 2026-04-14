"""KpiCard — widget reutilizavel para exibir um KPI do dashboard."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel

from src.desktop.theme import COLORS


class KpiCard(QFrame):
    """Card com titulo, valor numerico e barra superior colorida."""

    COLOR_MAP = {
        "green": "green",
        "blue": "accent",
        "yellow": "yellow",
        "red": "red",
        "orange": "orange",
        "muted": "muted",
    }

    def __init__(self, title: str, color: str = "blue", parent=None):
        super().__init__(parent)
        self.setObjectName("KpiCard")
        color_key = self.COLOR_MAP.get(color, "accent")
        accent = COLORS.get(color_key, COLORS["accent"])

        self.setStyleSheet(f"""
            QFrame#KpiCard {{
                background: {COLORS['card']};
                border: 1px solid {COLORS['border']};
                border-top: 3px solid {accent};
                border-radius: 8px;
                padding: 16px;
                min-width: 140px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        self._title = QLabel(title)
        self._title.setStyleSheet(f"color: {COLORS['muted']}; font-size: 11px; font-weight: bold;")
        self._title.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._value = QLabel("0")
        self._value.setStyleSheet(
            f"color: {accent}; font-size: 28px; font-weight: bold; "
            f"font-family: 'Consolas', monospace;"
        )
        self._value.setAlignment(Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(self._title)
        layout.addWidget(self._value)

    def set_value(self, value) -> None:
        """Atualiza o valor exibido."""
        if isinstance(value, float):
            self._value.setText(f"R$ {value:,.2f}")
        else:
            self._value.setText(str(value))
