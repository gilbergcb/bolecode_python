"""
jobs/registrar_boletos.py — Consome fila PENDENTE/ERRO e registra no Bradesco.

Fluxo por titulo:
1. Reserva o registro (status -> PROCESSANDO)
2. Gera nosso_numero via sequence Oracle
3. Monta payload com dados do Oracle (armazenados em dados_oracle CLOB)
4. Chama API Bradesco
5. Salva retorno (nosso_numero, tx_id, qrcode_emv, linha_digitavel, cod_barras)
6. Status -> REGISTRADO  (ou ERRO se falhar)
"""
from __future__ import annotations

import json
from datetime import datetime

from loguru import logger

from src.db.oracle import stg_query, stg_execute, next_nosso_numero, log_service_event
from src.config import MAX_TENTATIVAS

from pathlib import Path
from src import config as _cfg

def _bradesco_ready() -> bool:
    """Verifica se certificados Bradesco existem antes de tentar registrar."""
    try:
        cert = Path(_cfg.BRADESCO_CERT_PEM)
        key = Path(_cfg.BRADESCO_KEY_PEM)
        client_id = _cfg.BRADESCO_CLIENT_ID
        if not cert.exists() or not key.exists():
            return False
        if client_id in ("", "seu_client_id"):
            return False
        return True
    except Exception:
        return False


def _parse_dados(dados_oracle) -> dict:
    if isinstance(dados_oracle, str):
        return json.loads(dados_oracle)
    if dados_oracle is None:
        return {}
    # oracledb LOB
    if hasattr(dados_oracle, "read"):
        return json.loads(dados_oracle.read())
    return dados_oracle


def run_registrar() -> int:
    """Processa boletos pendentes. Retorna qtd processada."""
    if not _bradesco_ready():
        return 0

    pendentes = stg_query(
        """
        SELECT * FROM (
            SELECT id, numtransvenda, prest, duplic, codfilial, numcar,
                   dtemissao, dtvenc, valor, codcob, dados_oracle,
                   nosso_numero, tentativas
            FROM boletos
            WHERE status IN ('PENDENTE', 'ERRO')
              AND NVL(modo_cobranca, 'BOLETO_HIBRIDO') = 'BOLETO_HIBRIDO'
              AND tentativas < :max_tent
            ORDER BY dtvenc ASC
        ) WHERE ROWNUM <= 20
        """,
        {"max_tent": MAX_TENTATIVAS},
    )

    if not pendentes:
        return 0

    processados = 0
    for b in pendentes:
        _processar_boleto(b)
        processados += 1

    return processados


def _processar_boleto(b: dict) -> None:
    from src.api.bradesco_client import registrar_boleto, BradescoAPIError
    bid = b["id"]
    dados = _parse_dados(b["dados_oracle"])

    # Marca como PROCESSANDO
    affected = stg_execute(
        """
        UPDATE boletos SET status='PROCESSANDO', tentativas = tentativas + 1
        WHERE id = :bid AND status IN ('PENDENTE', 'ERRO')
        """,
        {"bid": bid},
    )
    if not affected:
        return

    # Gera nosso_numero se ainda nao existe
    nosso_numero = b["nosso_numero"] or next_nosso_numero()
    if not b["nosso_numero"]:
        stg_execute(
            "UPDATE boletos SET nosso_numero = :nn WHERE id = :bid",
            {"nn": nosso_numero, "bid": bid},
        )

    # Dados do sacado vindos do Oracle
    nome = dados.get("nome_cliente", "CLIENTE")
    endereco = dados.get("endereco", "RUA NAO INFORMADA")
    cep_raw = str(dados.get("cep", "00000000")).replace("-", "").replace(".", "")
    cep = cep_raw[:5] if len(cep_raw) >= 5 else cep_raw.zfill(5)
    compl_cep = cep_raw[5:8] if len(cep_raw) > 5 else "000"
    municipio = dados.get("municipio", "MUNICIPIO")
    uf = str(dados.get("uf", "SP"))[:2]
    cpf_cnpj_raw = str(dados.get("cpf_cnpj", "00000000000000")).replace(".", "").replace("/", "").replace("-", "")
    ind_cpf_cnpj = "2" if len(cpf_cnpj_raw.lstrip("0")) > 11 else "1"

    seu_numero = f"{b['duplic'] or b['numtransvenda']}-{b['prest']}"
    data_emissao = b["dtemissao"]
    data_vencimento = b["dtvenc"]
    valor = float(b["valor"])

    payload_enviado = {
        "nosso_numero": nosso_numero,
        "seu_numero": seu_numero,
        "data_emissao": str(data_emissao),
        "data_vencimento": str(data_vencimento),
        "valor": valor,
    }

    try:
        resp = registrar_boleto(
            nosso_numero=nosso_numero,
            seu_numero=seu_numero,
            data_emissao=data_emissao,
            data_vencimento=data_vencimento,
            valor=valor,
            nome_sacado=nome,
            endereco_sacado=endereco,
            numero_sacado=dados.get("numero", "0"),
            cep_sacado=cep,
            complemento_cep=compl_cep,
            bairro_sacado=dados.get("bairro", ""),
            municipio_sacado=municipio,
            uf_sacado=uf,
            ind_cpf_cnpj_sacado=ind_cpf_cnpj,
            cpf_cnpj_sacado=cpf_cnpj_raw,
        )

        qrcode_emv = resp.get("wqrcdPdraoMercd") or resp.get("qrcode_emv")
        tx_id = resp.get("txId") or resp.get("tx_id")
        linha_digitavel = resp.get("linhaDigitavel") or resp.get("linha_digitavel")
        cod_barras = resp.get("codBarras") or resp.get("cod_barras")
        nosso_numero_retorno = resp.get("ctitloCobrCdent", nosso_numero)

        stg_execute(
            """
            UPDATE boletos SET
                status              = 'REGISTRADO',
                nosso_numero        = :nosso_numero,
                tx_id               = :tx_id,
                qrcode_emv          = :qrcode_emv,
                linha_digitavel     = :linha_digitavel,
                cod_barras          = :cod_barras,
                dt_registro_bradesco = :dt_reg,
                payload_enviado     = :payload_env,
                payload_recebido    = :payload_rec,
                ultimo_erro         = NULL
            WHERE id = :bid
            """,
            {
                "nosso_numero": nosso_numero_retorno,
                "tx_id": tx_id,
                "qrcode_emv": qrcode_emv,
                "linha_digitavel": linha_digitavel,
                "cod_barras": cod_barras,
                "dt_reg": datetime.utcnow(),
                "payload_env": json.dumps(payload_enviado),
                "payload_rec": json.dumps(resp),
                "bid": bid,
            },
        )
        logger.success(
            f"Boleto registrado: {b['numtransvenda']}/{b['prest']} "
            f"nosso_numero={nosso_numero_retorno} qr={'sim' if qrcode_emv else 'nao'}"
        )
        log_service_event("INFO", "Boleto registrado no Bradesco", {
            "numtransvenda": b["numtransvenda"],
            "nosso_numero": nosso_numero_retorno,
            "qrcode": bool(qrcode_emv),
        })

    except BradescoAPIError as exc:
        _marcar_erro(bid, f"API {exc.status_code}: {exc.body}", payload_enviado)
    except Exception as exc:
        _marcar_erro(bid, str(exc), payload_enviado)


def _marcar_erro(bid, msg: str, payload: dict) -> None:
    logger.error(f"Erro ao registrar boleto {bid}: {msg}")
    stg_execute(
        """
        UPDATE boletos SET
            status          = 'ERRO',
            ultimo_erro     = :erro,
            payload_enviado = :payload
        WHERE id = :bid
        """,
        {"erro": msg[:4000], "payload": json.dumps(payload), "bid": bid},
    )
    log_service_event("ERROR", "Falha ao registrar boleto", {"id": str(bid), "erro": msg[:500]})
