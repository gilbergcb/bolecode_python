"""BoletosTab — tabela completa com filtros, paginacao e acoes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableView, QHeaderView, QMessageBox,
)

from src.desktop.models.boletos_model import BoletosTableModel
from src.desktop.services.data_service import DataService
from src.desktop.widgets.qr_dialog import QrDialog
from src.desktop.theme import COLORS


class BoletosTab(QWidget):
    """Tab com listagem de boletos, filtros e acoes."""

    PAGE_SIZE = 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self._offset = 0
        self._total = 0
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Filtros ────────────────────────────
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        filter_row.addWidget(QLabel("Status:"))
        self._combo_status = QComboBox()
        self._combo_status.addItems([
            "Todos", "PENDENTE", "PROCESSANDO", "REGISTRADO",
            "ERRO", "CANCELADO", "BAIXADO",
        ])
        self._combo_status.setMinimumWidth(140)
        filter_row.addWidget(self._combo_status)

        filter_row.addWidget(QLabel("Filial:"))
        self._combo_filial = QComboBox()
        self._combo_filial.addItem("Todas")
        self._combo_filial.setMinimumWidth(100)
        self._combo_filial.setEditable(True)
        filter_row.addWidget(self._combo_filial)

        btn_filter = QPushButton("Filtrar")
        btn_filter.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']}; color: white; border: none;
                padding: 8px 18px; border-radius: 6px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #1d4ed8; }}
        """)
        btn_filter.clicked.connect(self._apply_filter)
        filter_row.addWidget(btn_filter)

        filter_row.addStretch()
        layout.addLayout(filter_row)

        # ── Tabela ─────────────────────────────
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
        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table, 1)

        # ── Paginacao + Acoes ──────────────────
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self._lbl_page = QLabel("0 boletos")
        self._lbl_page.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")
        bottom_row.addWidget(self._lbl_page)

        bottom_row.addStretch()

        self._btn_prev = QPushButton("<< Anterior")
        self._btn_prev.clicked.connect(self._prev_page)
        self._btn_prev.setEnabled(False)
        bottom_row.addWidget(self._btn_prev)

        self._btn_next = QPushButton("Proximo >>")
        self._btn_next.clicked.connect(self._next_page)
        self._btn_next.setEnabled(False)
        bottom_row.addWidget(self._btn_next)

        bottom_row.addSpacing(20)

        btn_qr = QPushButton("Ver QR Code")
        btn_qr.clicked.connect(self._show_qr)
        bottom_row.addWidget(btn_qr)

        btn_reprocess = QPushButton("Reprocessar")
        btn_reprocess.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['card']}; color: {COLORS['yellow']};
                border: 1px solid {COLORS['yellow']}; padding: 8px 18px;
                border-radius: 6px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {COLORS['border']}; }}
        """)
        btn_reprocess.clicked.connect(self._reprocessar)
        bottom_row.addWidget(btn_reprocess)

        layout.addLayout(bottom_row)

    # ── Data ───────────────────────────────────

    def refresh(self) -> None:
        """Busca boletos com filtros e paginacao atuais."""
        status = self._combo_status.currentText()
        if status == "Todos":
            status = ""
        filial = self._combo_filial.currentText()
        if filial == "Todas":
            filial = ""

        result = DataService.get_boletos(
            status=status, codfilial=filial,
            limit=self.PAGE_SIZE, offset=self._offset,
        )
        self._total = result.get("total", 0)
        self._model.set_data(result.get("boletos", []))
        self._update_pagination()

    def update_data(self, data: dict) -> None:
        """Chamado pelo refresh periodico com dados ja carregados."""
        self._total = data.get("total", 0)
        self._model.set_data(data.get("boletos", []))
        self._update_pagination()

    def _update_pagination(self) -> None:
        page = (self._offset // self.PAGE_SIZE) + 1
        total_pages = max(1, (self._total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self._lbl_page.setText(
            f"{self._total} boletos — pagina {page}/{total_pages}"
        )
        self._btn_prev.setEnabled(self._offset > 0)
        self._btn_next.setEnabled(self._offset + self.PAGE_SIZE < self._total)

    # ── Slots ──────────────────────────────────

    def _apply_filter(self) -> None:
        self._offset = 0
        self.refresh()

    def _prev_page(self) -> None:
        self._offset = max(0, self._offset - self.PAGE_SIZE)
        self.refresh()

    def _next_page(self) -> None:
        self._offset += self.PAGE_SIZE
        self.refresh()

    def _selected_row(self) -> dict | None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._model.get_row(indexes[0].row())

    def _on_double_click(self, index) -> None:
        row = self._model.get_row(index.row())
        if row:
            self._open_qr(row)

    def _show_qr(self) -> None:
        row = self._selected_row()
        if not row:
            return
        detail = DataService.get_boleto_detail(
            row["numtransvenda"], row["prest"]
        )
        if detail:
            self._open_qr(detail)

    def _open_qr(self, row: dict) -> None:
        dlg = QrDialog(
            str(row.get("numtransvenda", "")),
            str(row.get("prest", "")),
            row.get("qrcode_emv", "") or "",
            row.get("linha_digitavel", "") or "",
            row.get("cod_barras", "") or "",
            parent=self,
        )
        dlg.exec()

    def _reprocessar(self) -> None:
        row = self._selected_row()
        if not row:
            return
        if row.get("status") != "ERRO":
            QMessageBox.information(
                self, "Info", "Apenas boletos com status ERRO podem ser reprocessados."
            )
            return
        ok = DataService.reprocessar(row["numtransvenda"], row["prest"])
        if ok:
            QMessageBox.information(self, "Sucesso", "Boleto enviado para reprocessamento.")
            self.refresh()
        else:
            QMessageBox.warning(self, "Aviso", "Nao foi possivel reprocessar.")
