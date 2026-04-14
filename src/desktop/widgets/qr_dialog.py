"""QrDialog — modal para exibir QR Code EMV do boleto Pix."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QApplication, QTextEdit,
)

from src.desktop.theme import COLORS


class QrDialog(QDialog):
    """Exibe o QR Code EMV (texto) com opcao de copiar."""

    def __init__(self, numtransvenda: str, prest: str, qrcode_emv: str,
                 linha_digitavel: str = "", cod_barras: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"QR Code — Venda {numtransvenda} / {prest}")
        self.setMinimumWidth(500)
        self.setStyleSheet(f"""
            QDialog {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Titulo
        title = QLabel(f"Boleto {numtransvenda} / {prest}")
        title.setStyleSheet(f"color: {COLORS['text']}; font-size: 16px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # QR Code EMV
        if qrcode_emv:
            self._add_section(layout, "QR Code EMV (Pix Copia e Cola)", qrcode_emv)

        # Linha digitavel
        if linha_digitavel:
            self._add_section(layout, "Linha Digitavel", linha_digitavel)

        # Codigo de barras
        if cod_barras:
            self._add_section(layout, "Codigo de Barras", cod_barras)

        # Fechar
        btn_close = QPushButton("Fechar")
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #1d4ed8; }}
        """)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

    def _add_section(self, parent_layout: QVBoxLayout, label: str, text: str) -> None:
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {COLORS['muted']}; font-size: 11px; font-weight: bold;")
        parent_layout.addWidget(lbl)

        txt = QTextEdit()
        txt.setPlainText(text)
        txt.setReadOnly(True)
        txt.setMaximumHeight(80)
        txt.setFont(QFont("Consolas", 10))
        txt.setStyleSheet(f"""
            QTextEdit {{
                background: {COLORS['card']};
                border: 1px solid {COLORS['border']};
                color: {COLORS['text']};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        parent_layout.addWidget(txt)

        btn_copy = QPushButton(f"Copiar {label}")
        btn_copy.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['card']};
                color: {COLORS['muted']};
                border: 1px solid {COLORS['border']};
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background: {COLORS['border']}; color: {COLORS['text']}; }}
        """)
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(text))

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn_copy)
        parent_layout.addLayout(row)
