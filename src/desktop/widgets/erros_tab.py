"""ErrosTab — tabela de boletos com erro e acoes de reprocessamento."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableView, QHeaderView, QMessageBox,
)

from src.desktop.models.boletos_model import BoletosTableModel
from src.desktop.services.data_service import DataService


class ErrosTab(QWidget):
    """Tab dedicada a boletos com status ERRO."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        from src.desktop.theme import COLORS
        title = QLabel("Boletos com Erro")
        title.setStyleSheet(
            f"color: {COLORS['red']}; font-size: 16px; font-weight: bold;"
        )
        header.addWidget(title)

        self._lbl_count = QLabel("0 erros")
        self._lbl_count.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")
        header.addWidget(self._lbl_count, alignment=Qt.AlignmentFlag.AlignVCenter)

        header.addStretch()

        btn_all = QPushButton("Reprocessar Todos")
        btn_all.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['red']}; color: white; border: none;
                padding: 8px 18px; border-radius: 6px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #b91c1c; }}
        """)
        btn_all.clicked.connect(self._reprocessar_todos)
        header.addWidget(btn_all)

        layout.addLayout(header)

        # Tabela
        self._model = BoletosTableModel()
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self._table, 1)

        # Acoes individual
        action_row = QHBoxLayout()
        action_row.addStretch()

        btn_reprocess = QPushButton("Reprocessar Selecionado")
        btn_reprocess.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['card']}; color: {COLORS['yellow']};
                border: 1px solid {COLORS['yellow']}; padding: 8px 18px;
                border-radius: 6px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {COLORS['border']}; }}
        """)
        btn_reprocess.clicked.connect(self._reprocessar_selecionado)
        action_row.addWidget(btn_reprocess)

        layout.addLayout(action_row)

    def refresh(self) -> None:
        """Busca boletos com status ERRO."""
        result = DataService.get_boletos(status="ERRO", limit=200)
        self._model.set_data(result.get("boletos", []))
        count = result.get("total", 0)
        self._lbl_count.setText(f"{count} erros")

    def update_data(self, data: dict) -> None:
        """Atualiza a partir de dados do refresh periodico (filtra erros)."""
        boletos = data.get("boletos", [])
        erros = [b for b in boletos if b.get("status") == "ERRO"]
        self._model.set_data(erros)
        self._lbl_count.setText(f"{len(erros)} erros")

    def _reprocessar_selecionado(self) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return
        row = self._model.get_row(indexes[0].row())
        if not row:
            return
        ok = DataService.reprocessar(row["numtransvenda"], row["prest"])
        if ok:
            QMessageBox.information(self, "Sucesso", "Boleto enviado para reprocessamento.")
            self.refresh()
        else:
            QMessageBox.warning(self, "Aviso", "Nao foi possivel reprocessar.")

    def _reprocessar_todos(self) -> None:
        reply = QMessageBox.question(
            self, "Confirmar",
            "Reprocessar TODOS os boletos com erro?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            count = DataService.reprocessar_todos_erros()
            QMessageBox.information(
                self, "Resultado",
                f"{count} boletos enviados para reprocessamento.",
            )
            self.refresh()
