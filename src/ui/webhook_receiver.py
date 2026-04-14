"""
ui/webhook_receiver.py — Endpoint para receber notificacoes de pagamento do Bradesco.

Requisitos do Bradesco para webhook em producao:
  - Certificado SSL do tipo EV ou OV (nao DV)
  - CN do certificado = URL do endpoint
  - TLS 1.2 ou superior
  - Metodo POST
  - Cadastrar URL via: POST /boleto/cobranca-webhook/v1/executar
"""
from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException, status
from loguru import logger

from src.db.oracle import stg_query, stg_execute, execute_oracle, log_service_event

router = APIRouter(prefix="/webhook", tags=["webhook"])

CANAL_PAGAMENTO = {
    "1": "Agencia",
    "2": "Terminal de Autoatendimento",
    "3": "Internet Banking",
    "4": "PIX",
    "5": "Correspondente Bancario",
    "6": "Call Center",
    "7": "Arquivo Eletronico",
    "8": "DDA",
}


@router.post("/bradesco/pagamento", status_code=status.HTTP_200_OK)
async def receber_pagamento(request: Request):
    """Endpoint de callback para notificacoes de pagamento do Bradesco."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Body invalido")

    tipo_evento = body.get("tipoEvento")
    if tipo_evento != "P":
        return {"status": "ignored", "motivo": f"tipoEvento={tipo_evento}"}

    nosso_numero = str(body.get("nossoNumero", "")).strip()
    if not nosso_numero:
        raise HTTPException(400, "nossoNumero ausente")

    canal = CANAL_PAGAMENTO.get(str(body.get("canalPagamento", "")), "Desconhecido")
    valor_pago = body.get("valorPagamento", "0")
    data_pgto = body.get("dataPagamento")

    logger.info(
        f"Webhook pagamento recebido: nosso_numero={nosso_numero} "
        f"canal={canal} valor={valor_pago} data={data_pgto}"
    )

    # Busca boleto no staging Oracle
    rows = stg_query(
        "SELECT id, numtransvenda, prest FROM boletos WHERE nosso_numero = :nn",
        {"nn": nosso_numero},
    )
    if not rows:
        logger.warning(f"Webhook: nosso_numero {nosso_numero} nao encontrado no staging.")
        log_service_event("WARN", "Webhook: nosso_numero nao encontrado", {"nosso_numero": nosso_numero})
        return {"status": "not_found"}

    b = rows[0]

    # Atualiza status no BOLETOS
    stg_execute(
        "UPDATE boletos SET status = 'BAIXADO' WHERE id = :bid",
        {"bid": b["id"]},
    )

    # Marca pagamento no PCPREST (Winthor)
    try:
        execute_oracle(
            """
            UPDATE PCPREST
               SET DTPAG = TO_DATE(:dtpag, 'YYYY-MM-DD')
            WHERE NUMTRANSVENDA = :n AND PREST = :p AND DTPAG IS NULL
            """,
            {
                "dtpag": data_pgto,
                "n": b["numtransvenda"],
                "p": str(b["prest"]),
            },
        )
        logger.success(
            f"Webhook: baixa aplicada — "
            f"NUMTRANSVENDA={b['numtransvenda']} PREST={b['prest']}"
        )
    except Exception as exc:
        logger.error(f"Webhook: falha ao baixar no Oracle: {exc}")
        log_service_event("ERROR", "Webhook: falha na baixa Oracle", {
            "nosso_numero": nosso_numero,
            "erro": str(exc),
        })

    log_service_event("INFO", f"Pagamento via webhook: {nosso_numero}", {
        "canal": canal,
        "valor_pago": valor_pago,
        "numtransvenda": b["numtransvenda"],
    })

    return {"status": "ok", "nossoNumero": nosso_numero}
