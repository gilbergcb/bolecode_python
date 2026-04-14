"""
widgets/cobranca_tab.py — Tab Cobranca do SettingsDialog.

Permite parametrizar quais CODCOBs do Winthor (PCCOB) serao
tratados como Boleto Hibrido e quais como PIX Cobranca (COBV).

Fluxo:
  1. Botao "Carregar da PCCOB" le todas as cobrancas do Winthor
  2. Exibe tabela com CODCOB, descricao, flags (BOLETO, DEPOSITO)
  3. Usuario marca checkboxes em colunas "Boleto" e "PIX"
  4. Botao "Salvar" grava na tabela CONFIGURACOES do schema BOLECODE

Chaves gravadas:
  - CODCOB_BOLETO   = "237,BK"   (virgula-separado)
  - CODCOB_PIX      = "PIX,DP"   (virgula-separado)
  - CODFILIAIS      = "1,2,3"    (virgula-separado)
  - PIX_VALIDADE_APOS_VENCIMENTO = "30"
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRunnable, QThreadPool, Signal, QObject, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QSpinBox, QMessageBox, QLineEdit, QFormLayout, QGroupBox,
    QApplication,
)

from src.desktop.theme import COLORS


class _WorkerSignals(QObject):
    """Signals para workers async."""
    finished = Signal(object)
    error = Signal(str)


class _OracleWorker(QRunnable):
    """Executa query Oracle em thread separada para nao travar a UI."""
    def __init__(self, fn, *args):
        super().__init__()
        self.fn = fn
        self.args = args
        self.signals = _WorkerSignals()

    @Slot()
    def run(self):
        try:
            result = self.fn(*self.args)
            self.signals.finished.emit(result)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class CobrancaTab(QWidget):
    """Tab para parametrizar CODCOBs de boleto e PIX."""

    # Colunas da tabela PCCOB
    COL_CODCOB = 0
    COL_DESCRICAO = 1
    COL_BOLETO_FLAG = 2
    COL_PIX_FLAG = 3
    COL_SEL_BOLETO = 4
    COL_SEL_PIX = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        # Carrega valores salvos em background (nao trava a UI)
        self._load_saved_async()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── Header ────────────────────────────────────────
        info = QLabel(
            "Selecione os codigos de cobranca (PCCOB) para cada modalidade.\n"
            "Use 'Carregar da PCCOB' para buscar do Winthor."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 12px;")
        layout.addWidget(info)

        # ── Botao carregar ────────────────────────────────
        btn_row = QHBoxLayout()
        self._btn_load = btn_load = QPushButton("Carregar da PCCOB")
        btn_load.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                color: white; border: none;
                padding: 8px 16px; border-radius: 5px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #1d4ed8; }}
        """)
        btn_load.clicked.connect(self._carregar_pccob)
        btn_row.addWidget(btn_load)

        # Campo de pesquisa
        self._search = QLineEdit()
        self._search.setPlaceholderText("Pesquisar por codigo ou descricao...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._filter_table)
        btn_row.addWidget(self._search, 1)

        layout.addLayout(btn_row)

        # ── Tabela PCCOB ──────────────────────────────────
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "CODCOB", "Descricao", "BOLETO", "DEPOSITO", "Usar Boleto", "Usar PIX",
        ])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        layout.addWidget(self._table, 1)

        # ── Filiais ───────────────────────────────────────
        filiais_group = QGroupBox("Filiais Monitoradas")
        filiais_layout = QFormLayout(filiais_group)
        self._filiais_edit = QLineEdit()
        self._filiais_edit.setPlaceholderText("1,2,3 (separar por virgula)")
        filiais_layout.addRow("CODFILIAL:", self._filiais_edit)
        layout.addWidget(filiais_group)

        # ── Cobranças Configuradas (resumo salvo) ─────────
        saved_group = QGroupBox("Cobrancas Configuradas")
        saved_layout = QVBoxLayout(saved_group)
        saved_layout.setSpacing(6)

        self._saved_table = QTableWidget(0, 3)
        self._saved_table.setHorizontalHeaderLabels(["CODCOB", "Descricao", "Modalidade"])
        sh = self._saved_table.horizontalHeader()
        sh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        sh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        sh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._saved_table.verticalHeader().setVisible(False)
        self._saved_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._saved_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._saved_table.setAlternatingRowColors(True)
        self._saved_table.setMaximumHeight(150)
        saved_layout.addWidget(self._saved_table)

        self._lbl_saved_empty = QLabel("Nenhuma cobranca configurada. Carregue da PCCOB e salve.")
        self._lbl_saved_empty.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; padding: 8px;")
        self._lbl_saved_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        saved_layout.addWidget(self._lbl_saved_empty)

        layout.addWidget(saved_group)

        # ── Configs inferiores (lado a lado) ──────────────
        bottom_row = QHBoxLayout()

        # Filiais
        filiais_group = QGroupBox("Filiais Monitoradas")
        filiais_layout = QFormLayout(filiais_group)
        self._filiais_edit = QLineEdit()
        self._filiais_edit.setPlaceholderText("1,2,3 (separar por virgula)")
        filiais_layout.addRow("CODFILIAL:", self._filiais_edit)
        bottom_row.addWidget(filiais_group)

        # PIX Validade
        pix_group = QGroupBox("PIX Cobranca")
        pix_layout = QFormLayout(pix_group)
        self._validade_spin = QSpinBox()
        self._validade_spin.setRange(1, 365)
        self._validade_spin.setSuffix(" dias")
        self._validade_spin.setValue(30)
        pix_layout.addRow("Validade apos vencimento:", self._validade_spin)
        bottom_row.addWidget(pix_group)

        layout.addLayout(bottom_row)

    def _carregar_pccob(self) -> None:
        """Busca registros da tabela PCCOB no Winthor Oracle (em background)."""
        self._btn_load.setEnabled(False)
        self._btn_load.setText("Carregando...")

        def _query():
            from src.db.oracle import query_oracle
            # Tenta via sinonimo/tabela local
            try:
                return query_oracle("""
                    SELECT CODCOB, COBRANCA,
                           NVL(BOLETO, 'N') AS BOLETO,
                           NVL(DEPOSITOBANCARIO, 'N') AS DEPOSITOBANCARIO
                    FROM PCCOB
                    ORDER BY CODCOB
                """)
            except Exception:
                pass
            # Fallback: descobre owner e qualifica
            rows = query_oracle("""
                SELECT owner FROM all_tables
                WHERE table_name = 'PCCOB' AND ROWNUM = 1
            """)
            if not rows:
                raise RuntimeError(
                    "Tabela PCCOB nao encontrada. Verifique se o usuario "
                    "BOLECODE tem GRANT SELECT na PCCOB do Winthor."
                )
            owner = rows[0]["owner"]
            return query_oracle(f"""
                SELECT CODCOB, COBRANCA,
                       NVL(BOLETO, 'N') AS BOLETO,
                       NVL(DEPOSITOBANCARIO, 'N') AS DEPOSITOBANCARIO
                FROM {owner}.PCCOB
                ORDER BY CODCOB
            """)

        worker = _OracleWorker(_query)
        worker.signals.finished.connect(self._on_pccob_loaded)
        worker.signals.error.connect(self._on_pccob_error)
        QThreadPool.globalInstance().start(worker)

    def _on_pccob_error(self, msg: str) -> None:
        self._btn_load.setEnabled(True)
        self._btn_load.setText("Carregar da PCCOB")
        QMessageBox.critical(self, "Erro", f"Nao foi possivel carregar PCCOB:\n{msg}")

    def _on_pccob_loaded(self, rows) -> None:
        self._btn_load.setEnabled(True)
        self._btn_load.setText("Carregar da PCCOB")

        if not rows:
            QMessageBox.information(self, "Vazio", "Nenhuma cobranca encontrada na PCCOB.")
            return

        # Preserva selecoes anteriores
        prev_boleto, prev_pix = self._get_selected()

        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            codcob = str(row.get("codcob", ""))
            descricao = str(row.get("cobranca", ""))
            flag_boleto = str(row.get("boleto", "N"))
            flag_deposito = str(row.get("depositobancario", "N"))

            # Dados somente leitura
            item_cod = QTableWidgetItem(codcob)
            item_cod.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(i, self.COL_CODCOB, item_cod)

            item_desc = QTableWidgetItem(descricao)
            item_desc.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(i, self.COL_DESCRICAO, item_desc)

            item_bol = QTableWidgetItem(flag_boleto)
            item_bol.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item_bol.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, self.COL_BOLETO_FLAG, item_bol)

            item_dep = QTableWidgetItem(flag_deposito)
            item_dep.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item_dep.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, self.COL_PIX_FLAG, item_dep)

            # Checkboxes selecionaveis
            cb_boleto = QCheckBox()
            cb_boleto.setChecked(codcob in prev_boleto)
            self._table.setCellWidget(i, self.COL_SEL_BOLETO, self._center_widget(cb_boleto))

            cb_pix = QCheckBox()
            cb_pix.setChecked(codcob in prev_pix)
            self._table.setCellWidget(i, self.COL_SEL_PIX, self._center_widget(cb_pix))

        self._table.resizeRowsToContents()

    def _filter_table(self, text: str) -> None:
        """Filtra linhas da tabela por CODCOB ou Descricao."""
        termo = text.strip().upper()
        for i in range(self._table.rowCount()):
            if not termo:
                self._table.setRowHidden(i, False)
                continue
            codcob = (self._table.item(i, self.COL_CODCOB) or QTableWidgetItem("")).text().upper()
            desc = (self._table.item(i, self.COL_DESCRICAO) or QTableWidgetItem("")).text().upper()
            match = termo in codcob or termo in desc
            self._table.setRowHidden(i, not match)

    def _center_widget(self, widget: QWidget) -> QWidget:
        """Wrappa widget num container centralizado para uso em celula de tabela."""
        container = QWidget()
        hl = QHBoxLayout(container)
        hl.addWidget(widget)
        hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.setContentsMargins(0, 0, 0, 0)
        return container

    def _get_selected(self) -> tuple[set[str], set[str]]:
        """Retorna sets de CODCOBs selecionados para boleto e PIX."""
        boleto_set: set[str] = set()
        pix_set: set[str] = set()
        for i in range(self._table.rowCount()):
            codcob_item = self._table.item(i, self.COL_CODCOB)
            if not codcob_item:
                continue
            codcob = codcob_item.text()

            w_bol = self._table.cellWidget(i, self.COL_SEL_BOLETO)
            if w_bol:
                cb = w_bol.findChild(QCheckBox)
                if cb and cb.isChecked():
                    boleto_set.add(codcob)

            w_pix = self._table.cellWidget(i, self.COL_SEL_PIX)
            if w_pix:
                cb = w_pix.findChild(QCheckBox)
                if cb and cb.isChecked():
                    pix_set.add(codcob)

        return boleto_set, pix_set

    def _load_saved_async(self) -> None:
        """Carrega valores salvos na CONFIGURACOES em background."""
        def _fetch():
            from src.db.oracle import get_config, query_oracle
            codcobs_boleto = get_config("CODCOB_BOLETO", "")
            codcobs_pix = get_config("CODCOB_PIX", "")

            # Busca descricoes da PCCOB para os CODCOBs salvos
            all_codes = [c.strip() for c in (codcobs_boleto + "," + codcobs_pix).split(",") if c.strip()]
            desc_map = {}
            if all_codes:
                in_clause = ",".join(f"'{c}'" for c in all_codes)
                try:
                    rows = query_oracle(f"SELECT CODCOB, COBRANCA FROM PCCOB WHERE CODCOB IN ({in_clause})")
                    desc_map = {str(r["codcob"]): str(r.get("cobranca", "")) for r in rows}
                except Exception:
                    pass  # sem descricao, mostra so o codigo

            return {
                "filiais": get_config("CODFILIAIS", ""),
                "validade": get_config("PIX_VALIDADE_APOS_VENCIMENTO", "30"),
                "codcobs_boleto": codcobs_boleto,
                "codcobs_pix": codcobs_pix,
                "desc_map": desc_map,
            }

        worker = _OracleWorker(_fetch)
        worker.signals.finished.connect(self._on_saved_loaded)
        worker.signals.error.connect(lambda _: None)
        QThreadPool.globalInstance().start(worker)

    def _on_saved_loaded(self, data: dict) -> None:
        self._filiais_edit.setText(data.get("filiais", ""))
        try:
            self._validade_spin.setValue(int(data.get("validade", "30")))
        except (ValueError, TypeError):
            pass

        # Popula tabela de cobranças configuradas
        self._populate_saved_table(
            data.get("codcobs_boleto", ""),
            data.get("codcobs_pix", ""),
            data.get("desc_map", {}),
        )

    def _populate_saved_table(self, codcobs_boleto: str, codcobs_pix: str, desc_map: dict) -> None:
        """Preenche a tabela resumo das cobranças salvas."""
        items: list[tuple[str, str, str]] = []
        for c in [x.strip() for x in codcobs_boleto.split(",") if x.strip()]:
            items.append((c, desc_map.get(c, ""), "Boleto Hibrido"))
        for c in [x.strip() for x in codcobs_pix.split(",") if x.strip()]:
            items.append((c, desc_map.get(c, ""), "PIX Cobranca"))

        has_items = len(items) > 0
        self._saved_table.setVisible(has_items)
        self._lbl_saved_empty.setVisible(not has_items)

        if not has_items:
            self._saved_table.setRowCount(0)
            return

        self._saved_table.setRowCount(len(items))
        for i, (codcob, desc, modo) in enumerate(items):
            item_cod = QTableWidgetItem(codcob)
            item_cod.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._saved_table.setItem(i, 0, item_cod)

            item_desc = QTableWidgetItem(desc)
            item_desc.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._saved_table.setItem(i, 1, item_desc)

            item_modo = QTableWidgetItem(modo)
            item_modo.setFlags(Qt.ItemFlag.ItemIsEnabled)
            # Cor por modalidade
            if "PIX" in modo:
                item_modo.setForeground(QColor(COLORS["green"]))
            else:
                item_modo.setForeground(QColor(COLORS["accent"]))
            self._saved_table.setItem(i, 2, item_modo)

        self._saved_table.resizeRowsToContents()

    def save(self) -> bool:
        """Salva configuracoes na tabela CONFIGURACOES. Retorna True se ok."""
        boleto_set, pix_set = self._get_selected()

        # Validacao: um CODCOB nao pode estar em ambos
        overlap = boleto_set & pix_set
        if overlap:
            QMessageBox.warning(
                self, "Conflito",
                f"Os seguintes CODCOBs estao marcados em ambos:\n{', '.join(overlap)}\n\n"
                "Cada CODCOB deve pertencer a apenas uma modalidade.",
            )
            return False

        filiais = self._filiais_edit.text().strip()
        validade = str(self._validade_spin.value())

        try:
            from src.db.oracle import set_config
            codcob_boleto_str = ",".join(sorted(boleto_set))
            codcob_pix_str = ",".join(sorted(pix_set))
            set_config("CODCOB_BOLETO", codcob_boleto_str,
                        "CODCOBs para Boleto Hibrido")
            set_config("CODCOB_PIX", codcob_pix_str,
                        "CODCOBs para PIX Cobranca COBV")
            if filiais:
                set_config("CODFILIAIS", filiais, "Filiais monitoradas")
            set_config("PIX_VALIDADE_APOS_VENCIMENTO", validade,
                        "Dias de validade PIX apos vencimento")

            # Atualiza tabela de configurados com descricoes da tabela PCCOB
            desc_map = {}
            for i in range(self._table.rowCount()):
                cod_item = self._table.item(i, self.COL_CODCOB)
                desc_item = self._table.item(i, self.COL_DESCRICAO)
                if cod_item:
                    desc_map[cod_item.text()] = desc_item.text() if desc_item else ""
            self._populate_saved_table(codcob_boleto_str, codcob_pix_str, desc_map)

            return True
        except Exception as exc:
            QMessageBox.critical(
                self, "Erro",
                f"Nao foi possivel salvar configuracoes:\n{exc}",
            )
            return False
