"""
ui/api_routes.py — FastAPI (webhook-only mode).

Com o desktop PySide6, os endpoints REST do dashboard nao sao mais
necessarios. Mantemos apenas:
  - /webhook/bradesco/pagamento  (boleto — Bradesco precisa de endpoint HTTP)
  - /webhook/pix/pagamento       (PIX — padrao BACEN)
  - /health                      (monitoramento basico)
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.ui.webhook_receiver import router as webhook_router
from src.ui.pix_webhook_receiver import handle_pix_webhook

app = FastAPI(title="BOLECODE Webhook", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)


@app.post("/webhook/pix/pagamento")
async def pix_pagamento(request: Request):
    """Endpoint de callback para notificacoes de pagamento PIX (padrao BACEN)."""
    return await handle_pix_webhook(request)


@app.get("/health")
def health():
    return {"status": "ok"}
