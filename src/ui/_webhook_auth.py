"""
ui/_webhook_auth.py — Autenticacao de webhooks via header compartilhado.

O Bradesco envia um header customizado com o secret configurado no cadastro
do webhook. Em sandbox, se DASHBOARD_SECRET estiver com valor default, a
validacao e ignorada (warning no log).

Header esperado: X-Webhook-Secret: <DASHBOARD_SECRET>
"""
from __future__ import annotations

import hmac

from fastapi import Request, HTTPException, status
from loguru import logger

from src.config import DASHBOARD_SECRET, BRADESCO_ENV

# Secrets que nao devem ser aceitos em producao
_UNSAFE_DEFAULTS = {"bolecode-dev-secret", "", "troque_por_segredo_forte_aqui"}

_HEADER_NAME = "X-Webhook-Secret"


def _is_production() -> bool:
    return BRADESCO_ENV == "producao"


def _secret_is_safe() -> bool:
    return DASHBOARD_SECRET not in _UNSAFE_DEFAULTS


def verify_webhook_secret(request: Request) -> None:
    """FastAPI Dependency — valida header X-Webhook-Secret.

    Em sandbox com secret default: loga warning mas permite (dev local).
    Em producao com secret default: rejeita TODAS as requisicoes.
    """
    if not _secret_is_safe():
        if _is_production():
            logger.critical(
                "DASHBOARD_SECRET com valor inseguro em PRODUCAO! "
                "Todas as requisicoes de webhook serao rejeitadas. "
                "Configure um secret forte no .env."
            )
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Webhook desabilitado: secret nao configurado",
            )
        # Sandbox: permite sem validacao mas avisa
        logger.warning(
            "Webhook sem autenticacao (DASHBOARD_SECRET com valor default). "
            "Configure um secret forte antes de ir para producao."
        )
        return

    received = request.headers.get(_HEADER_NAME, "")
    if not received:
        logger.warning(f"Webhook rejeitado: header {_HEADER_NAME} ausente")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Header de autenticacao ausente")

    if not hmac.compare_digest(received, DASHBOARD_SECRET):
        logger.warning(f"Webhook rejeitado: secret invalido")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Secret invalido")


def check_webhook_secret(request: Request) -> None:
    """Versao funcional (nao-Depends) para uso em handlers manuais."""
    verify_webhook_secret(request)
