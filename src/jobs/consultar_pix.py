"""
jobs/consultar_pix.py — Consulta COBVs registrados para detectar pagamentos.

Complementa o webhook PIX — caso a notificacao falhe, este job
consulta periodicamente o status dos COBVs no Bradesco.

Status COBV Bradesco:
  ATIVA      → aguardando pagamento
  CONCLUIDA  → paga
  REMOVIDA_PELO_USUARIO_RECEBEDOR → cancelada pelo recebedor
  REMOVIDA_PELO_PSP → cancelada pelo Bradesco
"""
from __future__ import annotations

from datetime import datetime

from loguru import logger

from src.db.oracle import stg_query, stg_execute, execute_oracle, log_service_event

from pathlib import Path
from src import config as _cfg


def _pix_ready() -> bool:
    """Verifica se certificados e chave PIX existem."""
    try:
        cert = Path(_cfg.BRADESCO_CERT_PEM)
        key = Path(_cfg.BRADESCO_KEY_PEM)
        if not cert.exists() or not key.exists():
            return False
        if not _cfg.BRADESCO_ALIAS_PIX:
            return False
        return True
    except Exception:
        return False


def run_consultar_pix() -> int:
    """Consulta COBVs REGISTRADO para detectar pagamentos. Retorna qtd atualizada."""
    if not _pix_ready():
        return 0

    from src.api.pix_client import consultar_cobv, PixAPIError

    registrados = stg_query("""
        SELECT * FROM (
            SELECT id, tx_id, numtransvenda, prest, valor, codfilial
            FROM boletos
            WHERE status = 'REGISTRADO'
              AND NVL(modo_cobranca, 'BOLETO_HIBRIDO') = 'PIX_COBV'
              AND tx_id IS NOT NULL
            ORDER BY dtvenc ASC
        ) WHERE ROWNUM <= 100
    """)

    if not registrados:
        return 0

    pagos = 0
    for b in registrados:
        try:
            resp = consultar_cobv(b["tx_id"])
            status_cobv = resp.get("status", "")

            if status_cobv == "CONCLUIDA":
                _marcar_pago(b, resp)
                pagos += 1
            elif status_cobv in ("REMOVIDA_PELO_USUARIO_RECEBEDOR", "REMOVIDA_PELO_PSP"):
                stg_execute(
                    "UPDATE boletos SET status = 'CANCELADO' WHERE id = :bid",
                    {"bid": b["id"]},
                )
                logger.info(f"PIX COBV cancelado: {b['numtransvenda']}/{b['prest']} status={status_cobv}")

        except PixAPIError as exc:
            if exc.status_code == 404:
                logger.debug(f"COBV nao encontrado: {b['tx_id']}")
            else:
                logger.warning(f"Erro ao consultar COBV {b['tx_id']}: {exc}")
        except Exception as exc:
            logger.warning(f"Erro ao consultar COBV {b['tx_id']}: {exc}")

    if pagos:
        logger.info(f"consultar_pix: {pagos} pagamento(s) detectado(s).")
        log_service_event("INFO", f"Consulta PIX: {pagos} pagamentos detectados", {})

    return pagos


def _marcar_pago(b: dict, resp: dict) -> None:
    """Atualiza boleto como BAIXADO e faz writeback na PCPREST."""
    bid = b["id"]

    # Atualiza status na staging
    stg_execute(
        """
        UPDATE boletos SET
            status = 'BAIXADO',
            updated_at = SYSTIMESTAMP
        WHERE id = :bid AND status = 'REGISTRADO'
        """,
        {"bid": bid},
    )

    # Writeback PCPREST (DTPAG)
    try:
        execute_oracle(
            """
            UPDATE PCPREST
               SET DTPAG = :dtpag
            WHERE NUMTRANSVENDA = :numtransvenda
              AND PREST = :prest
              AND DTPAG IS NULL
            """,
            {
                "dtpag": datetime.utcnow(),
                "numtransvenda": b["numtransvenda"],
                "prest": str(b["prest"]),
            },
        )
    except Exception as exc:
        logger.error(f"Erro writeback PCPREST PIX {b['numtransvenda']}/{b['prest']}: {exc}")

    logger.success(
        f"PIX pago detectado: {b['numtransvenda']}/{b['prest']} txid={b['tx_id']}"
    )
    log_service_event("INFO", "Pagamento PIX detectado via consulta", {
        "numtransvenda": b["numtransvenda"],
        "prest": str(b["prest"]),
        "txid": b["tx_id"],
    })
