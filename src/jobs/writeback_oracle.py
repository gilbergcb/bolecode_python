"""
jobs/writeback_oracle.py — Grava QRCODE_PIX de volta em PCPREST no Winthor.

Busca boletos REGISTRADO com oracle_atualizado=0 na tabela BOLETOS
(schema BOLECODE) e executa UPDATE no PCPREST (schema Winthor via sinonimo).
"""
from __future__ import annotations

from loguru import logger

from src.db.oracle import stg_query, stg_execute, execute_oracle, log_service_event

WINTHOR_UPDATE = """
UPDATE PCPREST
   SET QRCODE_PIX   = :qrcode,
       NOSSONUMBCO   = :nosso_numero
WHERE NUMTRANSVENDA = :numtransvenda
  AND PREST         = :prest
"""


def run_writeback() -> int:
    """Escreve QR Code nos titulos ja registrados. Retorna qtd atualizada."""
    pendentes = stg_query(
        """
        SELECT id, numtransvenda, prest, nosso_numero, qrcode_emv
        FROM boletos
        WHERE status = 'REGISTRADO'
          AND oracle_atualizado = 0
          AND qrcode_emv IS NOT NULL
          AND ROWNUM <= 50
        """,
    )

    if not pendentes:
        return 0

    atualizados = 0
    for b in pendentes:
        qrcode = b["qrcode_emv"]
        # LOB -> string
        if hasattr(qrcode, "read"):
            qrcode = qrcode.read()

        try:
            rows = execute_oracle(
                WINTHOR_UPDATE,
                {
                    "qrcode": str(qrcode)[:4000],
                    "nosso_numero": b["nosso_numero"],
                    "numtransvenda": b["numtransvenda"],
                    "prest": str(b["prest"]),
                },
            )
            stg_execute(
                "UPDATE boletos SET oracle_atualizado = 1 WHERE id = :bid",
                {"bid": b["id"]},
            )
            atualizados += 1
            logger.debug(
                f"Writeback OK: NUMTRANSVENDA={b['numtransvenda']} "
                f"PREST={b['prest']} rows={rows}"
            )
        except Exception as exc:
            logger.error(
                f"Writeback FALHOU {b['numtransvenda']}/{b['prest']}: {exc}"
            )
            log_service_event("ERROR", "Falha no writeback Oracle", {
                "numtransvenda": b["numtransvenda"],
                "prest": str(b["prest"]),
                "erro": str(exc),
            })

    if atualizados:
        logger.info(f"writeback_oracle: {atualizados} titulo(s) atualizados no Winthor.")
        log_service_event("INFO", f"Writeback: {atualizados} QR Codes gravados no Oracle")

    return atualizados
