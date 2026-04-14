# BOLECODE — Monitor de Cobranças Bradesco (Python / Windows)

Aplicacao desktop PySide6 para Windows que monitora a tabela `PCPREST` do Winthor
(Oracle 19c), registra **Boletos Hibridos** e **PIX Cobranca COBV** na API Bradesco,
e devolve o QR Code EMV de volta ao Winthor — tudo de forma automatica e continua.

---

## Arquitetura

```
Winthor Oracle 19c (PCPREST)
        |  polling a cada 30s
        v
  Oracle staging (BOLECODE_BOLETOS)
        |  fila PENDENTE -> PROCESSANDO
        v
  API Bradesco (mTLS + OAuth2)
   |                        |
   | Boleto Hibrido         | PIX COBV (qrpix.bradesco.com.br)
   v                        v
  Oracle (status REGISTRADO + QR Code EMV)
        |  writeback a cada 20s
        v
  Winthor Oracle 19c (PCPREST.QRCODE_PIX)
```

**Banco unico**: Oracle 19c armazena tanto os dados Winthor quanto as tabelas de staging do BOLECODE (sem PostgreSQL).

**Dual mode**: O tipo de cobranca (Boleto vs PIX) e configuravel por CODCOB via tabela `CONFIGURACOES` e tela Settings.

---

## Pre-requisitos

| Componente | Versao minima |
|---|---|
| Windows | 10 / Server 2016 |
| Python | 3.11+ |
| Oracle Instant Client | 19c ou 21c (thick mode) |
| Certificado Bradesco | PEM (.crt + .key) — sandbox: autoassinado |

---

## Instalacao rapida

```bat
REM Execute o setup como Administrador
setup.bat
```

O script:
1. Cria venv em `.venv/`
2. Instala todas as dependencias
3. Abre `.env` no Notepad para configuracao

---

## Configuracao (.env)

Edite `.env` (copiado de `.env.example`) preenchendo:

```env
# Oracle / Winthor
ORACLE_HOST=192.168.1.253
ORACLE_PORT=1521
ORACLE_SERVICE=LOCAL
ORACLE_USER=LOCAL
ORACLE_PASSWORD=LOCAL
ORACLE_INSTANT_CLIENT_DIR=C:\oracle\instantclient_21_9

# Bradesco API
BRADESCO_ENV=sandbox          # ou: producao
BRADESCO_CLIENT_ID=...
BRADESCO_CLIENT_SECRET=...
BRADESCO_CERT_PEM=certs/bradesco.crt.pem
BRADESCO_KEY_PEM=certs/bradesco.key.pem

# Dados do beneficiario (contrato Bradesco)
BRADESCO_NRO_CPF_CNPJ_BENEF=68542653     # CNPJ raiz
BRADESCO_FIL_CPF_CNPJ_BENEF=1018
BRADESCO_DIG_CPF_CNPJ_BENEF=38
BRADESCO_CNEGOC_COBR=386100000000041000  # agencia(4)+zeros(7)+conta(7)
BRADESCO_ALIAS_PIX=                       # chave PIX do beneficiario (EVP ou CNPJ)

# PIX Cobranca (COBV)
PIX_VALIDADE_APOS_VENCIMENTO=30           # dias apos vencimento
```

---

## Executar

```bat
start.bat
```

Ou manualmente:

```bat
.venv\Scripts\activate
python main.py
```

A aplicacao desktop abre com 4 abas + icone no system tray.

---

## Estrutura de arquivos

```
bolecode/
├── main.py                              # Entry point (QApplication)
├── setup.bat                            # Setup automatico
├── start.bat                            # Inicializacao rapida
├── requirements.txt
├── .env.example
├── certs/                               # Certificados mTLS (gitignored)
├── logs/                                # Logs rotativos (gitignored)
└── src/
    ├── config.py                        # Variaveis de ambiente validadas
    ├── db/
    │   └── oracle.py                    # Pool Oracle (thick mode) + migrations
    ├── api/
    │   ├── bradesco_client.py           # Cliente HTTP mTLS (Boleto Hibrido)
    │   └── pix_client.py               # Cliente HTTP mTLS (PIX COBV)
    ├── jobs/
    │   ├── sync_pcprest.py              # Oracle PCPREST -> staging (monitor)
    │   ├── registrar_boletos.py         # Staging -> API Bradesco (Boleto)
    │   ├── registrar_pix.py             # Staging -> API Bradesco (PIX COBV)
    │   ├── writeback_oracle.py          # QR Code -> Oracle PCPREST
    │   ├── consultar_liquidados.py      # Deteccao pagamentos Boleto (polling)
    │   └── consultar_pix.py            # Deteccao pagamentos PIX (polling)
    ├── monitor/
    │   └── scheduler.py                 # APScheduler (orquestra os jobs)
    ├── desktop/
    │   ├── app.py                       # BolecodeApp (orquestracao PySide6)
    │   ├── main_window.py               # MainWindow (4 tabs + status bar)
    │   ├── tray.py                      # QSystemTrayIcon + toast notifications
    │   ├── theme.py                     # QSS dark/light themes
    │   ├── signals.py                   # SignalHub (ponte threads->UI)
    │   ├── models/
    │   │   ├── boletos_model.py         # QAbstractTableModel para boletos
    │   │   └── logs_model.py            # QAbstractTableModel para logs
    │   ├── services/
    │   │   ├── data_service.py          # Queries Oracle diretas (sem HTTP)
    │   │   └── refresh_worker.py        # QTimer + QThreadPool auto-refresh 15s
    │   └── widgets/
    │       ├── dashboard_tab.py         # KPIs + scheduler + filial bars
    │       ├── boletos_tab.py           # Tabela + filtros + paginacao + acoes
    │       ├── erros_tab.py             # Tabela erros + reprocessar
    │       ├── logs_tab.py              # Tabela logs
    │       ├── kpi_card.py              # Widget KPI reutilizavel
    │       ├── scheduler_card.py        # Widget status job reutilizavel
    │       ├── qr_dialog.py             # Modal QR Code EMV + copiar
    │       ├── cobranca_tab.py          # Config Boleto/PIX por CODCOB
    │       └── settings_dialog.py       # Dialog configuracoes
    └── ui/
        ├── api_routes.py                # FastAPI (webhook-only + health check)
        ├── webhook_receiver.py          # Callback Bradesco (Boleto)
        └── pix_webhook_receiver.py      # Callback Bradesco (PIX)
```

---

## Jobs automaticos

| Job | Intervalo | Descricao |
|---|---|---|
| sync_pcprest | 30s | Polling Oracle PCPREST -> staging |
| registrar_boletos | 15s | Fila PENDENTE -> API Bradesco (Boleto Hibrido) |
| registrar_pix | 15s | Fila PENDENTE -> API Bradesco (PIX COBV) |
| writeback_oracle | 20s | QR Code EMV -> Oracle PCPREST |
| consultar_liquidados | 60min | Polling pagamentos Boleto |
| consultar_pix | 60min | Polling pagamentos PIX |

---

## App Desktop (PySide6)

### 4 Abas
- **Dashboard**: 6 KPI cards, status dos jobs, grafico por filial, ultimos registrados
- **Boletos**: tabela completa + filtros (status, filial) + paginacao + Ver QR + Reprocessar
- **Erros**: tabela filtrada ERRO + reprocessar individual/todos
- **Logs**: ultimos registros de service_log com nivel colorido

### System Tray
- Icone colorido por status (azul=ativo, verde=ok, vermelho=erro)
- Menu: Mostrar | Pausar/Retomar | Sair
- Toast notifications nativas Windows
- Fechar janela (X) = minimiza para tray

### Settings Dialog
- Configuracao de cobranças: selecao Boleto/PIX por CODCOB (tabela PCCOB)
- Filiais monitoradas
- Validade PIX apos vencimento

---

## Webhook de pagamento (opcional)

Para receber notificacoes em tempo real:

| Tipo | Endpoint |
|---|---|
| Boleto | `POST /webhook/bradesco/pagamento` |
| PIX | `POST /webhook/pix/pagamento` |

Requisitos para producao:
- SSL tipo **EV ou OV** (nao DV)
- CN = URL do endpoint
- TLS 1.2+

---

## Observacoes importantes

| Ponto | Detalhe |
|---|---|
| Oracle thick mode | Necessario para Oracle 19c. Requer Instant Client no `ORACLE_INSTANT_CLIENT_DIR` |
| `PREST` e VARCHAR2(2) | Nunca converter para numero — sempre tratar como string |
| `vnmnalTitloCobr` | Valor em centavos sem decimal: R$ 50,00 -> `"5000"` |
| Token Bradesco | Validade 1h — reutilizado automaticamente, renovado 5 min antes |
| mTLS sandbox | Certificado A1 autoassinado aceito em sandbox |
| mTLS producao | Certificado A1 emitido por AC, CN com razao social + CNPJ |
| Idempotencia | MERGE INTO + nosso_numero UNIQUE evitam duplicatas |
| Banco unico | Oracle 19c armazena tudo (Winthor + staging BOLECODE), sem PostgreSQL |

---

## Licenca

Uso interno. Nao distribuir.
