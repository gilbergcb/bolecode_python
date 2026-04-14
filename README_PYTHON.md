# BOLECODE — Monitor de Cobrança Bradesco (Python / Windows)

Aplicação desktop para Windows que monitora a tabela `PCPREST` do Winthor
(Oracle 19c), registra boletos híbridos com QR Code PIX na API Bradesco e
devolve o código EMV de volta ao Winthor, tudo de forma automática e contínua.

---

## Arquitetura

```
Winthor Oracle 19c (PCPREST)
        │  polling a cada 30s
        ▼
  PostgreSQL staging (boletos)
        │  fila PENDENTE → PROCESSANDO
        ▼
  API Bradesco (mTLS + OAuth2)
        │  nosso_numero + QR Code EMV
        ▼
  PostgreSQL (status REGISTRADO)
        │  writeback a cada 20s
        ▼
  Winthor Oracle 19c (PCPREST.QRCODE_PIX)
```

---

## Pré-requisitos

| Componente | Versão mínima |
|---|---|
| Windows | 10 / Server 2016 |
| Python | 3.11+ |
| PostgreSQL | 14+ (pode ser local ou remoto) |
| Oracle Instant Client | 19c ou 21c |
| Certificado Bradesco | PEM (.crt + .key) — sandbox: autoassinado |

---

## Instalação rápida

```bat
REM Execute o setup como Administrador
setup.bat
```

O script:
1. Cria venv em `.venv/`
2. Instala todas as dependências
3. Abre `.env` no Notepad para configuração

---

## Configuração (.env)

Edite `.env` (copiado de `.env.example`) preenchendo:

```env
# Oracle / Winthor
ORACLE_HOST=192.168.1.253
ORACLE_PORT=1521
ORACLE_SERVICE=LOCAL
ORACLE_USER=LOCAL
ORACLE_PASSWORD=LOCAL
ORACLE_INSTANT_CLIENT_DIR=C:\oracle\instantclient_21_9

# PostgreSQL
PG_HOST=localhost
PG_DATABASE=bolecode
PG_USER=bolecode
PG_PASSWORD=bolecode123

# Bradesco
BRADESCO_ENV=sandbox          # ou: producao
BRADESCO_CLIENT_ID=...
BRADESCO_CLIENT_SECRET=...
BRADESCO_CERT_PEM=certs/bradesco.crt.pem
BRADESCO_KEY_PEM=certs/bradesco.key.pem

# Dados do beneficiário (contrato Bradesco)
BRADESCO_NRO_CPF_CNPJ_BENEF=68542653     # CNPJ raiz
BRADESCO_FIL_CPF_CNPJ_BENEF=1018
BRADESCO_DIG_CPF_CNPJ_BENEF=38
BRADESCO_CNEGOC_COBR=386100000000041000  # agência(4)+zeros(7)+conta(7)
```

---

## Executar (desenvolvimento)

```bat
start.bat
```

Ou manualmente:

```bat
.venv\Scripts\activate
python main.py
```

O dashboard abre automaticamente em: **http://localhost:8765**

---

## Instalar como Serviço Windows

```bat
REM Como Administrador:
.venv\Scripts\python install_service.py install
.venv\Scripts\python install_service.py start

REM Para parar / remover:
.venv\Scripts\python install_service.py stop
.venv\Scripts\python install_service.py remove
```

O serviço inicia automaticamente com o Windows e roda sem interface gráfica.
Para monitorar, acesse o dashboard via navegador: http://localhost:8765

---

## Estrutura de arquivos

```
bolecode/
├── main.py                        # Entry point
├── install_service.py             # Instalação como serviço Windows
├── setup.bat                      # Setup automático
├── start.bat                      # Inicialização rápida
├── requirements.txt
├── .env.example
├── certs/                         # Certificados mTLS (gitignored)
├── logs/                          # Logs rotativos (gitignored)
└── src/
    ├── config.py                  # Variáveis de ambiente validadas
    ├── db/
    │   ├── oracle.py              # Pool Oracle (thick mode)
    │   └── postgres.py            # Pool PG + migrations automáticas
    ├── api/
    │   └── bradesco_client.py     # Cliente HTTP mTLS + token cache
    ├── jobs/
    │   ├── sync_pcprest.py        # Oracle → PostgreSQL (monitor)
    │   ├── registrar_boletos.py   # PostgreSQL → API Bradesco
    │   ├── writeback_oracle.py    # QR Code → Oracle PCPREST
    │   └── consultar_liquidados.py # Detecção de pagamentos (polling)
    ├── monitor/
    │   └── scheduler.py           # APScheduler (orquestra os jobs)
    └── ui/
        ├── api_routes.py          # FastAPI (REST + SPA)
        ├── webhook_receiver.py    # Endpoint de callback Bradesco
        ├── tray.py                # Tray icon Windows (pystray)
        └── static/
            └── index.html         # Dashboard SPA
```

---

## Fluxo detalhado dos jobs

### sync_pcprest (a cada 30s)
Consulta `PCPREST JOIN PCCLIENT` no Oracle filtrando:
- `CODCOB = 237`
- `CODFILIAL = 1` (configurável)
- `QRCODE_PIX IS NULL`
- `DTPAG IS NULL`
- `DTVENC >= SYSDATE - 30`

Insere novos registros na tabela `boletos` do PostgreSQL com `ON CONFLICT DO NOTHING`.

### registrar_boletos (a cada 15s)
Para cada boleto com status `PENDENTE` ou `ERRO` (até 3 tentativas):
1. Gera `nosso_numero` via sequence PostgreSQL (11 dígitos, único)
2. Monta payload completo da API Bradesco com dados do sacado (de `dados_oracle` JSONB)
3. Chama `POST /boleto-hibrido/cobranca-registro/v1/gerarBoleto`
4. Salva `qrcode_emv` (EMV copy-paste), `tx_id`, `linha_digitavel`, `cod_barras`
5. Status → `REGISTRADO`

### writeback_oracle (a cada 20s)
Para cada boleto `REGISTRADO` com `oracle_atualizado = FALSE`:
- Executa `UPDATE PCPREST SET QRCODE_PIX = :qr, NOSSO_NUMERO = :nn WHERE ...`
- Marca `oracle_atualizado = TRUE` no PostgreSQL

### consultar_liquidados (a cada 60 min)
Alternativa ao webhook: consulta a API Bradesco por boletos pagos no dia e marca `BAIXADO`.

---

## Webhook de pagamento (opcional)

Para receber notificações em tempo real de pagamentos:

1. Cadastre a URL no Bradesco:
```
POST /boleto/cobranca-webhook/v1/executar
```
Com a URL: `https://seu-dominio.com/webhook/bradesco/pagamento`

2. Requisitos do certificado para produção:
   - SSL tipo **EV ou OV** (não DV)
   - CN = URL do endpoint
   - TLS 1.2+

O endpoint já está implementado em `src/ui/webhook_receiver.py`.

---

## Coluna QRCODE_PIX no Oracle

O campo `QRCODE_PIX` precisa existir em `PCPREST`. Se ainda não existe:

```sql
ALTER TABLE PCPREST ADD (
    QRCODE_PIX   VARCHAR2(4000),
    NOSSO_NUMERO VARCHAR2(11)
);
```

Execute como DBA no Oracle.

---

## Banco PostgreSQL

O PostgreSQL é usado como fila e staging. As migrations rodam automaticamente no boot.
Para criar o banco e usuário:

```sql
CREATE DATABASE bolecode;
CREATE USER bolecode WITH PASSWORD 'bolecode123';
GRANT ALL PRIVILEGES ON DATABASE bolecode TO bolecode;
```

---

## Observações importantes

| Ponto | Detalhe |
|---|---|
| Oracle thick mode | Necessário para Oracle 10g/19c. Requer Instant Client no `ORACLE_INSTANT_CLIENT_DIR` |
| `PREST` é VARCHAR2(2) | Nunca converter para número — sempre tratar como string |
| `vnmnalTitloCobr` | Valor em centavos sem decimal: R$ 50,00 → `"5000"` |
| Token Bradesco | Validade de 1h — reutilizado automaticamente, renovado 5 min antes |
| mTLS sandbox | Certificado A1 autoassinado aceito em sandbox |
| mTLS produção | Certificado A1 emitido por AC, CN com razão social + CNPJ |
| Idempotência | `ON CONFLICT DO NOTHING` + coluna `nosso_numero UNIQUE` evitam duplicatas |

---

## Licença

Uso interno. Não distribuir.
