"""DashboardTab — aba principal com KPIs, scheduler, filial e recentes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableView, QHeaderView, QScrollArea, QFrame,
)

from src.desktop.theme import COLORS
from src.desktop.widgets.kpi_card import KpiCard
from src.desktop.widgets.scheduler_card import SchedulerCard
from src.desktop.models.boletos_model import BoletosTableModel


class DashboardTab(QWidget):
    """Tab do dashboard com visao geral do sistema."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        # Scroll area para todo o conteudo
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # ── KPI Cards ──────────────────────────
        kpi_title = QLabel("Visao Geral")
        kpi_title.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 16px; font-weight: bold;"
        )
        main_layout.addWidget(kpi_title)

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        self.kpi_registrado = KpiCard("Registrados", "green")
        self.kpi_pendente = KpiCard("Pendentes", "blue")
        self.kpi_processando = KpiCard("Processando", "yellow")
        self.kpi_erro = KpiCard("Erros", "red")
        self.kpi_writeback = KpiCard("Writeback", "orange")
        self.kpi_total = KpiCard("Total", "muted")

        for card in [
            self.kpi_registrado, self.kpi_pendente, self.kpi_processando,
            self.kpi_erro, self.kpi_writeback, self.kpi_total,
        ]:
            kpi_row.addWidget(card)

        main_layout.addLayout(kpi_row)

        # ── Scheduler Cards ────────────────────
        sched_title = QLabel("Jobs do Scheduler")
        sched_title.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 14px; font-weight: bold;"
        )
        main_layout.addWidget(sched_title)

        sched_row = QHBoxLayout()
        sched_row.setSpacing(12)

        self.sched_sync = SchedulerCard("sync", "Sync Oracle")
        self.sched_registrar = SchedulerCard("registrar", "Registrar Boleto")
        self.sched_registrar_pix = SchedulerCard("registrar_pix", "Registrar PIX")
        self.sched_writeback = SchedulerCard("writeback", "Writeback Oracle")
        self.sched_liquidados = SchedulerCard("liquidados", "Liquidados Boleto")
        self.sched_consultar_pix = SchedulerCard("consultar_pix", "Liquidados PIX")

        for card in [
            self.sched_sync, self.sched_registrar, self.sched_registrar_pix,
            self.sched_writeback, self.sched_liquidados, self.sched_consultar_pix,
        ]:
            sched_row.addWidget(card)
        sched_row.addStretch()

        main_layout.addLayout(sched_row)

        # ── Por Filial ─────────────────────────
        filial_title = QLabel("Por Filial")
        filial_title.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 14px; font-weight: bold;"
        )
        main_layout.addWidget(filial_title)

        self._filial_container = QVBoxLayout()
        self._filial_container.setSpacing(4)
        main_layout.addLayout(self._filial_container)

        # ── Ultimos Registrados ────────────────
        recentes_title = QLabel("Ultimos 10 Registrados")
        recentes_title.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 14px; font-weight: bold;"
        )
        main_layout.addWidget(recentes_title)

        self._recentes_model = BoletosTableModel()
        self._recentes_table = QTableView()
        self._recentes_table.setModel(self._recentes_model)
        self._recentes_table.setAlternatingRowColors(True)
        self._recentes_table.setSelectionBehavior(
            QTableView.SelectionBehavior.SelectRows
        )
        self._recentes_table.verticalHeader().setVisible(False)
        self._recentes_table.horizontalHeader().setStretchLastSection(True)
        self._recentes_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._recentes_table.setMaximumHeight(320)
        main_layout.addWidget(self._recentes_table)

        main_layout.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Slots de atualizacao ───────────────────

    def update_kpis(self, data: dict) -> None:
        kpis = data.get("kpis", {})
        self.kpi_registrado.set_value(kpis.get("registrado", 0))
        self.kpi_pendente.set_value(kpis.get("pendente", 0))
        self.kpi_processando.set_value(kpis.get("processando", 0))
        self.kpi_erro.set_value(kpis.get("erro", 0))
        self.kpi_writeback.set_value(kpis.get("writeback_pendente", 0))
        self.kpi_total.set_value(kpis.get("total", 0))

    def update_scheduler(self, data: dict) -> None:
        sched = data.get("scheduler", {})
        self.sched_sync.update_status(
            sched.get("sync", "aguardando"), sched.get("sync_count", 0)
        )
        self.sched_registrar.update_status(
            sched.get("registrar", "aguardando"), sched.get("registrar_count", 0)
        )
        self.sched_registrar_pix.update_status(
            sched.get("registrar_pix", "aguardando"), sched.get("registrar_pix_count", 0)
        )
        self.sched_writeback.update_status(
            sched.get("writeback", "aguardando"), sched.get("writeback_count", 0)
        )
        self.sched_liquidados.update_status(
            sched.get("liquidados", "aguardando"), sched.get("liquidados_count", 0)
        )
        self.sched_consultar_pix.update_status(
            sched.get("consultar_pix", "aguardando"), sched.get("consultar_pix_count", 0)
        )

    def update_filiais(self, data: dict) -> None:
        por_filial = data.get("por_filial", [])
        # Limpa barras anteriores
        while self._filial_container.count():
            item = self._filial_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not por_filial:
            return

        max_total = max((f.get("total", 1) for f in por_filial), default=1) or 1

        for f in por_filial:
            row = QHBoxLayout()
            row.setSpacing(8)

            lbl = QLabel(f"Filial {f.get('codfilial', '?')}")
            lbl.setFixedWidth(80)
            lbl.setStyleSheet(f"color: {COLORS['muted']}; font-size: 12px;")

            # Bar container
            bar_frame = QFrame()
            bar_frame.setFixedHeight(22)
            bar_frame.setStyleSheet(
                f"background: {COLORS['border']}; border-radius: 4px; border: none;"
            )

            pct = int(f.get("total", 0) / max_total * 100)
            bar = QFrame(bar_frame)
            bar.setGeometry(0, 0, max(pct * 3, 4), 22)
            bar.setStyleSheet(f"background: {COLORS['accent']}; border-radius: 4px;")

            count_lbl = QLabel(
                f"{f.get('total', 0)} (R:{f.get('registrado', 0)} E:{f.get('erro', 0)})"
            )
            count_lbl.setStyleSheet(f"color: {COLORS['muted']}; font-size: 11px;")

            wrapper = QWidget()
            row_widget_layout = QHBoxLayout(wrapper)
            row_widget_layout.setContentsMargins(0, 0, 0, 0)
            row_widget_layout.setSpacing(8)
            row_widget_layout.addWidget(lbl)
            row_widget_layout.addWidget(bar_frame, 1)
            row_widget_layout.addWidget(count_lbl)

            self._filial_container.addWidget(wrapper)

    def update_recentes(self, data: dict) -> None:
        ultimos = data.get("ultimos", [])
        self._recentes_model.set_data(ultimos)

    def update_all(self, data: dict) -> None:
        """Atualiza todas as secoes de uma vez."""
        self.update_kpis(data)
        self.update_scheduler(data)
        self.update_filiais(data)
        self.update_recentes(data)
