"""DataService — acesso direto ao Oracle schema BOLECODE."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal

from src.db.oracle import stg_query, stg_execute, log_service_event
from src.monitor.scheduler import get_status as get_scheduler_status


def _serialize(val):
    """Converte tipos nao-JSON para serializacao."""
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, bytes):
        return val.hex()
    return val


def _serialize_row(row: dict) -> dict:
    return {k: _serialize(v) for k, v in row.items()}


class DataService:
    """Metodos estaticos para acesso a dados. Chamados do RefreshWorker."""

    @staticmethod
    def get_dashboard_data() -> dict:
        # KPIs
        kpi_rows = stg_query("""
            SELECT
                COUNT(CASE WHEN status = 'PENDENTE' THEN 1 END)    AS pendente,
                COUNT(CASE WHEN status = 'PROCESSANDO' THEN 1 END) AS processando,
                COUNT(CASE WHEN status = 'REGISTRADO' THEN 1 END)  AS registrado,
                COUNT(CASE WHEN status = 'ERRO' THEN 1 END)        AS erro,
                COUNT(CASE WHEN status = 'CANCELADO' THEN 1 END)   AS cancelado,
                COUNT(CASE WHEN status = 'BAIXADO' THEN 1 END)     AS baixado,
                COUNT(*)                                             AS total,
                NVL(SUM(CASE WHEN status = 'REGISTRADO' THEN valor END), 0) AS valor_registrado,
                COUNT(CASE WHEN status = 'REGISTRADO' AND oracle_atualizado = 0 THEN 1 END) AS writeback_pendente
            FROM boletos
        """)
        kpis = _serialize_row(kpi_rows[0]) if kpi_rows else {}

        # Por filial
        filial_rows = stg_query("""
            SELECT codfilial,
                   COUNT(*) AS total,
                   COUNT(CASE WHEN status = 'REGISTRADO' THEN 1 END) AS registrado,
                   COUNT(CASE WHEN status = 'ERRO' THEN 1 END) AS erro
            FROM boletos
            GROUP BY codfilial
            ORDER BY codfilial
        """)
        por_filial = [_serialize_row(r) for r in filial_rows]

        # Ultimos 10
        ultimos_rows = stg_query("""
            SELECT * FROM (
                SELECT numtransvenda, prest, codfilial, valor, status,
                       nosso_numero,
                       CASE WHEN qrcode_emv IS NOT NULL THEN 1 ELSE 0 END AS tem_qr,
                       dtvenc, created_at
                FROM boletos
                ORDER BY created_at DESC
            ) WHERE ROWNUM <= 10
        """)
        ultimos = [_serialize_row(r) for r in ultimos_rows]

        # Logs
        log_rows = stg_query("""
            SELECT * FROM (
                SELECT nivel, mensagem, created_at
                FROM service_log
                ORDER BY created_at DESC
            ) WHERE ROWNUM <= 20
        """)
        logs = [_serialize_row(r) for r in log_rows]

        # Scheduler
        scheduler = get_scheduler_status()

        return {
            "kpis": kpis,
            "por_filial": por_filial,
            "ultimos": ultimos,
            "logs": logs,
            "scheduler": scheduler,
        }

    @staticmethod
    def get_boletos(status: str = "", codfilial: str = "",
                    limit: int = 50, offset: int = 0) -> dict:
        conditions = []
        params: dict = {}

        if status:
            conditions.append("status = :status")
            params["status"] = status
        if codfilial:
            conditions.append("codfilial = :codfilial")
            params["codfilial"] = codfilial

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        total_rows = stg_query(
            f"SELECT COUNT(*) AS total FROM boletos {where}", params
        )
        total = int(total_rows[0]["total"]) if total_rows else 0

        params["row_max"] = offset + limit
        params["row_min"] = offset + 1

        rows = stg_query(f"""
            SELECT * FROM (
                SELECT a.*, ROWNUM rnum FROM (
                    SELECT id, numtransvenda, prest, codfilial, numcar, codcli,
                           dtemissao, dtvenc, valor, status, nosso_numero,
                           qrcode_emv, linha_digitavel, cod_barras,
                           oracle_atualizado, tentativas, ultimo_erro,
                           dt_registro_bradesco, created_at
                    FROM boletos {where}
                    ORDER BY created_at DESC
                ) a WHERE ROWNUM <= :row_max
            ) WHERE rnum >= :row_min
        """, params)

        return {
            "total": total,
            "boletos": [_serialize_row(r) for r in rows],
        }

    @staticmethod
    def get_boleto_detail(numtransvenda: int, prest: str) -> dict | None:
        rows = stg_query(
            "SELECT * FROM boletos WHERE numtransvenda = :ntv AND prest = :prest",
            {"ntv": numtransvenda, "prest": prest},
        )
        return _serialize_row(rows[0]) if rows else None

    @staticmethod
    def reprocessar(numtransvenda: int, prest: str) -> bool:
        count = stg_execute("""
            UPDATE boletos
            SET status = 'PENDENTE', tentativas = 0, ultimo_erro = NULL
            WHERE numtransvenda = :ntv AND prest = :prest AND status = 'ERRO'
        """, {"ntv": numtransvenda, "prest": prest})
        if count:
            log_service_event("INFO", f"Reprocessamento manual: {numtransvenda}/{prest}")
        return count > 0

    @staticmethod
    def reprocessar_todos_erros() -> int:
        count = stg_execute("""
            UPDATE boletos
            SET status = 'PENDENTE', tentativas = 0, ultimo_erro = NULL
            WHERE status = 'ERRO'
        """)
        if count:
            log_service_event("INFO", f"Reprocessamento em massa: {count} boletos")
        return count
