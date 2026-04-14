"""
ui/pix_webhook_receiver.py — Recebe notificacoes de pagamento PIX do Bradesco.

Payload padrao BACEN:
{
  "pix": [{
    "endToEndId": "EXXXX...",
    "txid": "...",
    "valor": "50.00",
    "horario": "2026-04-14T15:30:00.000Z",
    "pagador": {"cpf": "12345678901", "nome": "JOAO"}
  }]
}
"""
from __future__ import annotations

from datetime import datetime

from fastapi import Request
from loguru import logger

from src.db.oracle import stg_query, stg_execute, execute_oracle, log_service_event


async def handle_pix_webhook(request: Request) -> dict:
    """Processa notificacao de pagamento PIX do Bradesco."""
    try:
        body = await request.json()
    except Exception:
        logger.warning("PIX webhook: payload invalido")
        return {"status": "erro", "mensagem": "payload invalido"}

    pix_list = body.get("pix", [])
    if not isinstance(pix_list, list):
        logger.warning("PIX webhook: campo 'pix' nao e array")
        return {"status": "erro", "mensagem": "campo pix invalido"}

    processados = 0
    for pix in pix_list:
        txid = pix.get("txid")
        if not txid:
            continue

        end_to_end = pix.get("endToEndId", "")
        valor_str = pix.get("valor", "0")
        horario = pix.get("horario", "")
        pagador = pix.get("pagador", {})
        nome_pagador = pagador.get("nome", "")
        cpf_pagador = pagador.get("cpf", pagador.get("cnpj", ""))

        # Busca boleto pelo txid
        rows = stg_query(
            """
            SELECT id, numtransvenda, prest, status, codfilial
            FROM boletos
            WHERE tx_id = :txid
            """,
            {"txid": txid},
        )
        if not rows:
            logger.debug(f"PIX webhook: txid {txid} nao encontrado na staging")
            continue

        boleto = rows[0]
        if boleto["status"] == "BAIXADO":
            logger.debug(f"PIX webhook: txid {txid} ja esta BAIXADO")
            continue

        bid = boleto["id"]
        numtransvenda = boleto["numtransvenda"]
        prest = str(boleto["prest"])

        # Atualiza status para BAIXADO
        stg_execute(
            """
            UPDATE boletos SET
                status     = 'BAIXADO',
                updated_at = SYSTIMESTAMP
            WHERE id = :bid AND status != 'BAIXADO'
            """,
            {"bid": bid},
        )

        # Writeback PCPREST (DTPAG)
        try:
            dt_pagamento = datetime.utcnow()
            if horario:
                try:
                    dt_pagamento = datetime.fromisoformat(
                        horario.replace("Z", "+00:00")
                    )
                except Exception:
                    pass

            execute_oracle(
                """
                UPDATE PCPREST
                   SET DTPAG = :dtpag
                WHERE NUMTRANSVENDA = :numtransvenda
                  AND PREST = :prest
                  AND DTPAG IS NULL
                """,
                {
                    "dtpag": dt_pagamento,
                    "numtransvenda": numtransvenda,
                    "prest": prest,
                },
            )
        except Exception as exc:
            logger.error(f"Erro writeback PCPREST PIX {numtransvenda}/{prest}: {exc}")

        processados += 1
        logger.success(
            f"PIX pago via webhook: {numtransvenda}/{prest} "
            f"txid={txid} valor={valor_str} pagador={nome_pagador}"
        )
        log_service_event("INFO", "Pagamento PIX recebido via webhook", {
            "numtransvenda": numtransvenda,
            "prest": prest,
            "txid": txid,
            "valor": valor_str,
            "endToEndId": end_to_end,
            "pagador": nome_pagador,
        })

    return {"status": "ok", "processados": processados}
