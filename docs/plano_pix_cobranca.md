# Plano: PIX Cobranca com Vencimento (COBV) — Alternativa ao Boleto Hibrido

## Contexto

O BOLECODE hoje registra **boletos hibridos** no Bradesco (boleto + QR Code PIX embutido).
A nova funcionalidade adiciona **PIX Cobranca com Vencimento (COBV)** como alternativa:
gera apenas o QR Code PIX com data de vencimento, sem boleto bancario.

### Regra de Negocio: PCCOB define o modo

A decisao **boleto hibrido vs PIX COBV** e **por titulo**, determinada pelas
flags da tabela `PCCOB` do Winthor vinculada ao `CODCOB` da `PCPREST`:

```
PCCOB.BOLETO = 'S'              → titulo vai para Boleto Hibrido Bradesco
PCCOB.DEPOSITOBANCARIO = 'S'    → titulo vai para PIX Cobranca (COBV)
```

O CODCOB e arbitrario (237, BRD, PIX, 001...) — varia por empresa.
O que importa sao as flags na PCCOB, nao o codigo em si.

### Parametrizacao via Settings Dialog + CONFIGURACOES

O operador abre **Configuracoes → tab Cobranca** no desktop:
1. Clica "Carregar da PCCOB" → app consulta a PCCOB no Winthor
2. Ve a lista de CODCOBs com flags BOLETO e DEPOSITOBANCARIO
3. Marca quais quer monitorar (checkbox)
4. Salva → grava na tabela `CONFIGURACOES` do Oracle (schema BOLECODE)

```
CONFIGURACOES:
┌──────────────────────────────┬────────────────────────┐
│ CHAVE                        │ VALOR                  │
├──────────────────────────────┼────────────────────────┤
│ CODCOB_BOLETO                │ 237,BRD                │
│ CODCOB_PIX                   │ PIX,DEP                │
│ CODFILIAIS                   │ 1,2,5                  │
│ PIX_VALIDADE_APOS_VENCIMENTO │ 30                     │
└──────────────────────────────┴────────────────────────┘
```

O sync le da CONFIGURACOES (nao do .env) para saber quais CODCOBs buscar.
Se nenhum CODCOB_PIX estiver configurado, o fluxo PIX fica desabilitado.

---

## Documentacao de Referencia

| Documento | Conteudo |
|-----------|----------|
| `pixQRcode_manual.md` | Autenticacao OAuth2 para API PIX |
| `pixgeracaoQrcod.md` | CRUD completo: COB, **COBV**, locations, pix recebidos |
| `pix_Webhook.md` | Webhook PIX (notificacao de pagamento) |
| `doc_api_cobranca.md` | API Boleto Hibrido (atual) |

---

## Diferencas Tecnicas: Boleto Hibrido vs PIX COBV

| Aspecto | Boleto Hibrido (atual) | PIX COBV (novo) |
|---------|------------------------|-----------------|
| Endpoint | `/boleto-hibrido/.../gerarBoleto` | `/v2/cobv/{txid}` ou `/v2/cobv-emv/{txid}` |
| Host Producao | `openapi.bradesco.com.br` | `qrpix.bradesco.com.br` |
| Host Sandbox | `openapisandbox.prebanco.com.br` | `openapisandbox.prebanco.com.br` |
| Token endpoint | `/auth/server-mtls/v2/token` | `/auth/server/oauth/token` |
| Valor | Centavos sem decimal: `"5000"` | Decimal com ponto: `"50.00"` |
| Data | `dd.mm.aaaa` | `YYYY-MM-DD` (ISO 8601) |
| txid | Gerado pelo Bradesco | **Gerado pelo cliente** (26-35 chars alfanumerico) |
| Devedor | 15+ campos separados | Objeto simples {cpf/cnpj, nome, logradouro, cidade, uf, cep} |
| Multa/Juros | Campos numericos no payload boleto | Objetos estruturados com modalidade |
| Retorno QR | `wqrcdPdraoMercd` | `pixCopiaECola` |
| Retorno imagem | Nao tem | `/v2/cobv-emv/{txid}` retorna base64 da imagem |
| Gera boleto? | Sim (linha digitavel + cod barras) | Nao |
| Webhook | Endpoint hibrido `/boleto-hibrido/...` | Endpoint PIX `/v2/webhook/{chave_pix}` |
| Flag PCCOB | `BOLETO = 'S'` | `DEPOSITOBANCARIO = 'S'` |

---

## Arquitetura Proposta

```
    PCCOB (Winthor)                     CONFIGURACOES (BOLECODE)
    ┌────────────────────────┐          ┌───────────────────────────────┐
    │ CODCOB │ BOLETO │ DEP  │          │ CODCOB_BOLETO = 237,BRD      │
    │  237   │   S    │  N   │  ──────> │ CODCOB_PIX    = PIX          │
    │  PIX   │   N    │  S   │          │ CODFILIAIS    = 1,2          │
    │  341   │   S    │  N   │          └───────────┬───────────────────┘
    └────────────────────────┘                      │
         ▲                                          │
         │ Settings Dialog                          │
         │ "Carregar da PCCOB"                      ▼
         │ (checkbox selecao)              sync_pcprest.py (MODIFICADO)
                                           ├─ Le CODCOB_BOLETO e CODCOB_PIX da CONFIGURACOES
                                           ├─ WHERE p.CODCOB IN (:lista_boleto + :lista_pix)
                                           ├─ JOIN PCCOB para determinar MODO_COBRANCA
                                           │
                                           ▼
                                  BOLETOS (staging Oracle)
                         ┌────────────────┴─────────────────┐
                         │                                  │
              MODO = 'BOLETO_HIBRIDO'            MODO = 'PIX_COBV'
                         │                                  │
                         ▼                                  ▼
              registrar_boletos.py               registrar_pix.py (NOVO)
              bradesco_client.py                 pix_client.py (NOVO)
                         │                                  │
                         ▼                                  ▼
              writeback_oracle.py (sem mudanca — grava QRCODE_PIX na PCPREST)

    Webhooks (coexistem):
    ┌─────────────────────────────────────────────────────┐
    │ POST /webhook/bradesco/pagamento  → boleto hibrido  │
    │ POST /webhook/pix/pagamento       → PIX COBV (NOVO) │
    └─────────────────────────────────────────────────────┘
```

---

## Estrutura de Arquivos

### Arquivos Novos (6)

| Arquivo | Descricao | ~Linhas |
|---------|-----------|---------|
| `src/api/pix_client.py` | Cliente HTTP para API PIX COBV (token, mTLS, CRUD cobv) | ~250 |
| `src/jobs/registrar_pix.py` | Job: consome fila PIX_COBV e cria COBV no Bradesco | ~150 |
| `src/jobs/consultar_pix.py` | Job: consulta COBVs para detectar pagamentos | ~100 |
| `src/ui/pix_webhook_receiver.py` | Endpoint POST para receber webhook PIX do Bradesco | ~80 |
| `src/desktop/widgets/cobranca_tab.py` | Tab "Cobranca" no Settings Dialog (carregar PCCOB + selecionar) | ~200 |
| `docs/plano_pix_cobranca.md` | Este documento | — |

### Arquivos Modificados (8)

| Arquivo | Mudanca |
|---------|---------|
| `src/config.py` | +4 variaveis PIX (PIX_BASE_URL, PIX_TOKEN_URL, PIX_VALIDADE) |
| `src/db/oracle.py` | +3 colunas BOLETOS + sinonimo PCCOB + funcoes get/set CONFIGURACOES |
| `src/jobs/sync_pcprest.py` | Le CODCOBs da CONFIGURACOES; JOIN PCCOB; grava MODO_COBRANCA |
| `src/jobs/registrar_boletos.py` | Filtra WHERE modo_cobranca = 'BOLETO_HIBRIDO' |
| `src/monitor/scheduler.py` | Registrar jobs `registrar_pix` (15s) e `consultar_pix` (60min) |
| `src/ui/api_routes.py` | Adicionar rota `/webhook/pix/pagamento` |
| `src/desktop/widgets/settings_dialog.py` | Adicionar tab "Cobranca" com widget cobranca_tab |
| `.env.example` | Adicionar variaveis PIX (apenas host/token/validade) |

### Arquivos Intocados

- `src/api/bradesco_client.py` — client boleto nao muda
- `src/jobs/writeback_oracle.py` — grava QRCODE_PIX na PCPREST (serve ambos)
- `src/desktop/widgets/dashboard_tab.py` — KPIs ja contam por status
- `src/desktop/widgets/boletos_tab.py` — tabela ja mostra todos os boletos
- `src/desktop/widgets/qr_dialog.py` — ja exibe qrcode_emv (compativel)

---

## Fase 1 — Config + Schema Oracle

### 1.1 Novas variaveis em `src/config.py`

```python
# ── PIX API ──────────────────────────────────────────────
# Host diferente em producao (sandbox e o mesmo)
PIX_BASE_URL = (
    "https://openapisandbox.prebanco.com.br"
    if BRADESCO_ENV == "sandbox"
    else "https://qrpix.bradesco.com.br"
)

# Token endpoint PIX (diferente do boleto em producao)
PIX_TOKEN_URL = (
    "https://openapisandbox.prebanco.com.br/auth/server/oauth/token"
    if BRADESCO_ENV == "sandbox"
    else "https://qrpix.bradesco.com.br/auth/server/oauth/token"
)

# Validade apos vencimento (dias) para PIX COBV
PIX_VALIDADE_APOS_VENCIMENTO = int(os.getenv("PIX_VALIDADE_APOS_VENCIMENTO", "30"))
```

> **Nota**: As variaveis `WINTHOR_CODCOB` e `WINTHOR_CODFILIAL` continuam
> existindo como fallback. Porem a fonte principal passa a ser a tabela
> CONFIGURACOES (gerenciada pelo Settings Dialog).

### 1.2 Migracao Oracle — novas colunas em BOLETOS

```sql
-- Modo de cobranca (BOLETO_HIBRIDO ou PIX_COBV)
BEGIN
    EXECUTE IMMEDIATE
        'ALTER TABLE BOLETOS ADD MODO_COBRANCA VARCHAR2(20) DEFAULT ''BOLETO_HIBRIDO''';
EXCEPTION WHEN OTHERS THEN
    IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

-- Pix Copia e Cola (retorno COBV)
BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE BOLETOS ADD PIX_COPIA_E_COLA CLOB';
EXCEPTION WHEN OTHERS THEN
    IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

-- Imagem QR Code base64 (retorno cobv-emv)
BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE BOLETOS ADD QR_IMAGE_BASE64 CLOB';
EXCEPTION WHEN OTHERS THEN
    IF SQLCODE != -1430 THEN RAISE; END IF;
END;
/

-- Indice para filtro por modo
BEGIN
    EXECUTE IMMEDIATE
        'CREATE INDEX IDX_BOLETOS_MODO ON BOLETOS(MODO_COBRANCA)';
EXCEPTION WHEN OTHERS THEN
    IF SQLCODE != -955 THEN RAISE; END IF;
END;
/
```

### 1.3 Sinonimo PCCOB

```sql
-- Sinonimo para acessar PCCOB do schema Winthor
BEGIN
    EXECUTE IMMEDIATE 'CREATE OR REPLACE SYNONYM PCCOB FOR WINTHOR.PCCOB';
EXCEPTION WHEN OTHERS THEN NULL;
END;
/

-- Grant necessario (executar como DBA):
-- GRANT SELECT ON WINTHOR.PCCOB TO BOLECODE;
```

### 1.4 Funcoes get/set CONFIGURACOES em `oracle.py`

```python
def get_config(chave: str, default: str = "") -> str:
    """Le valor da tabela CONFIGURACOES."""
    rows = stg_query(
        "SELECT valor FROM configuracoes WHERE chave = :chave",
        {"chave": chave},
    )
    return rows[0]["valor"] if rows else default


def set_config(chave: str, valor: str, descricao: str = "") -> None:
    """Grava/atualiza valor na tabela CONFIGURACOES (MERGE)."""
    stg_execute("""
        MERGE INTO configuracoes tgt
        USING (SELECT :chave AS chave FROM DUAL) src
        ON (tgt.chave = src.chave)
        WHEN MATCHED THEN UPDATE SET valor = :valor
        WHEN NOT MATCHED THEN INSERT (chave, valor, descricao)
            VALUES (:chave, :valor, :descricao)
    """, {"chave": chave, "valor": valor, "descricao": descricao})


def get_codcobs_boleto() -> list[str]:
    """Retorna lista de CODCOBs configurados para boleto hibrido."""
    val = get_config("CODCOB_BOLETO", "")
    return [c.strip() for c in val.split(",") if c.strip()]


def get_codcobs_pix() -> list[str]:
    """Retorna lista de CODCOBs configurados para PIX COBV."""
    val = get_config("CODCOB_PIX", "")
    return [c.strip() for c in val.split(",") if c.strip()]


def get_codfiliais() -> list[str]:
    """Retorna lista de filiais configuradas para monitorar."""
    val = get_config("CODFILIAIS", config.WINTHOR_CODFILIAL)
    return [c.strip() for c in val.split(",") if c.strip()]
```

### 1.5 Atualizar `.env.example`

```env
# ── PIX Cobranca ─────────────────────────
PIX_VALIDADE_APOS_VENCIMENTO=30   # dias apos vencimento para aceitar pagamento PIX
# Host e token PIX sao derivados de BRADESCO_ENV automaticamente
# CODCOBs e filiais sao configurados no Settings Dialog (tab Cobranca)
```

---

## Fase 2 — Tab Cobranca no Settings Dialog

### 2.1 Novo widget `src/desktop/widgets/cobranca_tab.py`

```
┌─ Cobranca ──────────────────────────────────────────────────────┐
│                                                                  │
│  Filiais: [1, 2, 5          ]                                    │
│  Validade PIX apos venc: [30 ▼] dias                             │
│                                                                  │
│  [Carregar da PCCOB]                                             │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ ☑│☐  │ CODCOB │ Descricao         │ BOLETO │ DEP.BANC  │    │
│  ├──┼───┼────────┼───────────────────┼────────┼───────────┤    │
│  │ ☑│   │ 237    │ BRADESCO COBRANCA │   S    │     N     │    │
│  │  │ ☑ │ PIX    │ PIX BRADESCO      │   N    │     S     │    │
│  │ ☑│   │ BRD    │ BRADESCO CARTEIRA │   S    │     N     │    │
│  │  │   │ 341    │ ITAU COBRANCA     │   S    │     N     │    │
│  │  │   │ TED    │ TRANSFERENCIA     │   N    │     S     │    │
│  └──────────────────────────────────────────────────────────┘    │
│   Coluna 1: Boleto Hibrido    Coluna 2: PIX Cobranca            │
│                                                                  │
│  Selecionados:                                                   │
│    Boleto: 237, BRD                                              │
│    PIX:    PIX                                                   │
│                                                                  │
│                                         [Salvar]  [Cancelar]    │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Fluxo do widget

```python
class CobrancaTab(QWidget):
    """Tab de parametrizacao de cobranca — carrega PCCOB e salva em CONFIGURACOES."""

    def _carregar_pccob(self):
        """Consulta PCCOB no Winthor e popula a tabela."""
        rows = query_oracle("""
            SELECT CODCOB, COBRANCA, BOLETO, DEPOSITOBANCARIO
            FROM PCCOB
            ORDER BY CODCOB
        """)
        # Popula QTableWidget com checkboxes em 2 colunas:
        # col "Boleto" (check se BOLETO='S')
        # col "PIX"    (check se DEPOSITOBANCARIO='S')

    def _salvar(self):
        """Grava selecao na CONFIGURACOES."""
        boleto_codes = [row.codcob for row in checked_boleto]
        pix_codes = [row.codcob for row in checked_pix]
        filiais = self._txt_filiais.text()

        set_config("CODCOB_BOLETO", ",".join(boleto_codes),
                   "CODCOBs para boleto hibrido Bradesco")
        set_config("CODCOB_PIX", ",".join(pix_codes),
                   "CODCOBs para PIX Cobranca COBV")
        set_config("CODFILIAIS", filiais,
                   "Filiais a monitorar")
        set_config("PIX_VALIDADE_APOS_VENCIMENTO",
                   str(self._spin_validade.value()),
                   "Dias apos vencimento para PIX")

    def _load_saved(self):
        """Carrega selecao salva da CONFIGURACOES ao abrir."""
        boleto = get_config("CODCOB_BOLETO", "")
        pix = get_config("CODCOB_PIX", "")
        filiais = get_config("CODFILIAIS", config.WINTHOR_CODFILIAL)
        validade = get_config("PIX_VALIDADE_APOS_VENCIMENTO", "30")
```

### 2.3 Integrar no Settings Dialog

```python
# Em settings_dialog.py, _build_ui():
from src.desktop.widgets.cobranca_tab import CobrancaTab

self._cobranca_tab = CobrancaTab()
tabs.addTab(self._cobranca_tab, "Cobranca")
```

---

## Fase 3 — Sync PCPREST (modificado)

### 3.1 Query atualizada

```python
def run_sync() -> int:
    # Le CODCOBs configurados da CONFIGURACOES
    codcobs_boleto = get_codcobs_boleto()
    codcobs_pix = get_codcobs_pix()
    filiais = get_codfiliais()

    # Fallback: se nenhum configurado, usa .env (retrocompativel)
    if not codcobs_boleto and not codcobs_pix:
        codcobs_boleto = [config.WINTHOR_CODCOB]

    all_codcobs = codcobs_boleto + codcobs_pix
    if not all_codcobs:
        return 0

    # Monta IN clause dinamico (Oracle nao aceita bind em IN com lista)
    in_clause = ",".join(f"'{c}'" for c in all_codcobs)
    filial_clause = ",".join(f"'{f}'" for f in filiais) if filiais else f"'{config.WINTHOR_CODFILIAL}'"

    query = f"""
        SELECT
            p.NUMTRANSVENDA, p.PREST, p.DUPLIC, p.CODCLI,
            p.CODFILIAL, p.NUMCAR, p.DTEMISSAO, p.DTVENC,
            p.VALOR, p.CODCOB,
            c.CLIENTE AS NOME_CLIENTE,
            c.ENDERCOB AS ENDERECO,
            c.CEPCOB AS CEP,
            c.MUNICCOB AS MUNICIPIO,
            c.ESTCOB AS UF,
            c.CGCENT AS CPF_CNPJ,
            c.TELCOB AS TELEFONE
        FROM PCPREST p
        JOIN PCCLIENT c ON c.CODCLI = p.CODCLI
        WHERE p.CODCOB IN ({in_clause})
          AND p.CODFILIAL IN ({filial_clause})
          AND p.QRCODE_PIX IS NULL
          AND p.DTPAG IS NULL
          AND p.DTVENC >= TRUNC(SYSDATE) - 30
    """
```

### 3.2 MERGE atualizado com MODO_COBRANCA

```python
MERGE_BOLETO = """
MERGE INTO boletos tgt
USING (SELECT :numtransvenda AS ntv, :prest AS prest FROM DUAL) src
ON (tgt.numtransvenda = src.ntv AND tgt.prest = src.prest)
WHEN NOT MATCHED THEN INSERT
    (numtransvenda, prest, duplic, codcli, codfilial, numcar,
     dtemissao, dtvenc, valor, codcob, dados_oracle, status, modo_cobranca)
VALUES
    (:numtransvenda, :prest, :duplic, :codcli, :codfilial, :numcar,
     :dtemissao, :dtvenc, :valor, :codcob, :dados_oracle, 'PENDENTE', :modo_cobranca)
"""

# Determinar modo baseado no CODCOB
codcob = row["codcob"]
if codcob in codcobs_pix:
    modo = "PIX_COBV"
elif codcob in codcobs_boleto:
    modo = "BOLETO_HIBRIDO"
else:
    modo = "BOLETO_HIBRIDO"  # fallback
```

### 3.3 Retrocompatibilidade

Se a tabela CONFIGURACOES nao tem CODCOB_BOLETO nem CODCOB_PIX:
- Usa `WINTHOR_CODCOB` do `.env` (default "237") como boleto
- Nenhum PIX configurado → fluxo PIX desabilitado
- **Comportamento 100% identico ao atual**

---

## Fase 4 — Cliente PIX (`src/api/pix_client.py`)

### 4.1 Token PIX (separado do token boleto)

O token PIX usa endpoint diferente em producao (`qrpix.bradesco.com.br`).
Mesma logica de cache (55min TTL), mesmo cert mTLS, mesmo client_id/secret.

```python
_pix_token_cache = {"token": None, "expires_at": 0.0}

def _get_pix_token() -> str:
    """Obtem Bearer Token para API PIX (endpoint dedicado)."""
    url = config.PIX_TOKEN_URL
    with _build_mtls_client() as client:
        resp = client.post(url, data={
            "grant_type": "client_credentials",
            "client_id": config.BRADESCO_CLIENT_ID,
            "client_secret": config.BRADESCO_CLIENT_SECRET,
        })
    # cache 55 min
```

### 4.2 Gerar txid

No PIX COBV, o txid e **gerado pelo cliente** (26-35 chars alfanumerico).
Estrategia: `{timestamp_14}{cnpj_raiz_8}{seq_13}` = 35 chars

```python
def _gerar_txid() -> str:
    """Gera txid unico: YYYYMMDDHHMMSS + CNPJ_RAIZ(8) + SEQ(13)."""
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")  # 14 chars
    cnpj = config.BRADESCO_NRO_CPF_CNPJ_BENEF[:8]    # 8 chars
    seq = str(next_nosso_numero()).zfill(13)           # 13 chars
    return f"{ts}{cnpj}{seq}"                          # 35 chars
```

### 4.3 Funcoes principais

```python
def criar_cobv(txid, chave_pix, data_vencimento, valor, nome_devedor,
               cpf_cnpj_devedor, logradouro="", cidade="", uf="", cep="",
               validade_apos_vencimento=30, solicitacao_pagador="") -> dict:
    """PUT /v2/cobv/{txid} — Cria cobranca com vencimento."""

def criar_cobv_emv(txid, ..., nomePersonalizacaoQr="") -> dict:
    """PUT /v2/cobv-emv/{txid} — Cria COBV + retorna EMV + imagem base64."""

def consultar_cobv(txid: str) -> dict:
    """GET /v2/cobv/{txid} — Consulta status da cobranca."""

def revisar_cobv(txid: str, **campos) -> dict:
    """PATCH /v2/cobv/{txid} — Revisa cobranca (ex: cancelar)."""
```

### 4.4 Payload COBV (diferencas criticas do boleto)

```python
payload = {
    "calendario": {
        "dataDeVencimento": data_vencimento.strftime("%Y-%m-%d"),  # ISO 8601 (NAO dd.mm.aaaa)
        "validadeAposVencimento": validade_apos_vencimento,
    },
    "devedor": {
        "cpf": cpf_cnpj if len(cpf_cnpj) <= 11 else None,
        "cnpj": cpf_cnpj if len(cpf_cnpj) > 11 else None,
        "nome": nome_devedor[:200],
        "logradouro": logradouro[:200],
        "cidade": cidade[:200],
        "uf": uf[:2],
        "cep": cep[:8],
    },
    "valor": {
        "original": f"{valor:.2f}",   # "50.00" (NAO centavos como no boleto!)
    },
    "chave": chave_pix,
    "solicitacaopagador": solicitacao_pagador[:140],
}
# Remove None do devedor
payload["devedor"] = {k: v for k, v in payload["devedor"].items() if v}
```

---

## Fase 5 — Jobs PIX

### 5.1 `src/jobs/registrar_pix.py`

```
Fluxo:
1. Busca boletos PENDENTE/ERRO onde MODO_COBRANCA = 'PIX_COBV'
2. Reserva (status → PROCESSANDO)
3. Gera txid unico (_gerar_txid)
4. Monta payload com dados_oracle (nome, cpf, endereco)
5. Chama pix_client.criar_cobv_emv()
6. Salva retorno:
   - tx_id = txid (gerado por nos, nao pelo Bradesco)
   - pix_copia_e_cola = resp["pixCopiaECola"]
   - qrcode_emv = resp["pixCopiaECola"]  (compativel com QR dialog)
   - qr_image_base64 = resp.get("imagemQrcode")
7. Status → REGISTRADO (ou ERRO)
```

### 5.2 `src/jobs/consultar_pix.py`

Complementa o webhook — consulta periodicamente COBVs no Bradesco:

```python
def run_consultar_pix() -> int:
    registrados = stg_query("""
        SELECT * FROM (
            SELECT id, tx_id, numtransvenda, prest, valor
            FROM boletos
            WHERE status = 'REGISTRADO'
              AND modo_cobranca = 'PIX_COBV'
              AND tx_id IS NOT NULL
            ORDER BY dtvenc ASC
        ) WHERE ROWNUM <= 100
    """)
    pagos = 0
    for b in registrados:
        resp = consultar_cobv(b["tx_id"])
        if resp.get("status") == "CONCLUIDA":
            # Atualiza para BAIXADO + writeback PCPREST
            pagos += 1
    return pagos
```

### 5.3 Mudancas no `registrar_boletos.py`

Adicionar filtro `modo_cobranca = 'BOLETO_HIBRIDO'` na query de pendentes:

```python
# ANTES:
WHERE status IN ('PENDENTE', 'ERRO') AND tentativas < :max_tent

# DEPOIS:
WHERE status IN ('PENDENTE', 'ERRO')
  AND NVL(modo_cobranca, 'BOLETO_HIBRIDO') = 'BOLETO_HIBRIDO'
  AND tentativas < :max_tent
```

### 5.4 Registrar no scheduler

```python
# Em scheduler.py — adicionar junto aos jobs existentes:
from src.jobs.registrar_pix import run_registrar_pix
from src.jobs.consultar_pix import run_consultar_pix

scheduler.add_job(
    _wrap("registrar_pix", run_registrar_pix, "registrar_pix"),
    "interval", seconds=15,
    id="registrar_pix", replace_existing=True,
)
scheduler.add_job(
    _wrap("consultar_pix", run_consultar_pix, "pix"),
    "interval", minutes=60,
    id="consultar_pix", replace_existing=True,
)
```

---

## Fase 6 — Webhook PIX (`src/ui/pix_webhook_receiver.py`)

### 6.1 Endpoint

```python
@app.post("/webhook/pix/pagamento")
async def pix_webhook(request: Request):
    """Recebe notificacao de pagamento PIX do Bradesco (padrao BACEN)."""
```

### 6.2 Payload recebido

```json
{
  "pix": [{
    "endToEndId": "EXXXX...",
    "txid": "20260414685426530001234567890",
    "valor": "50.00",
    "horario": "2026-04-14T15:30:00.000Z",
    "pagador": { "cpf": "12345678901", "nome": "JOAO SILVA" }
  }]
}
```

### 6.3 Fluxo

```
1. Valida payload (array pix)
2. Para cada item em pix[]:
   a. Busca boleto por tx_id = pix.txid
   b. Se encontrou e status != BAIXADO:
      - Atualiza status → BAIXADO
      - Grava valor_pago, dt_pagamento, end_to_end_id
      - Faz writeback no PCPREST (DTPAG)
      - Emite signal payment_received
3. Retorna 200
```

### 6.4 Diferencas do webhook atual

| Aspecto | Webhook Boleto (atual) | Webhook PIX (novo) |
|---------|----------------------|---------------------|
| Rota | `/webhook/bradesco/pagamento` | `/webhook/pix/pagamento` |
| Identificador | `nossoNumero` | `txid` |
| Valor | `valorPagamento` | `pix[].valor` |
| Data | `dataPagamento` | `pix[].horario` |
| Pagador | Nao tem | `pix[].pagador.cpf/cnpj` |
| Formato | Objeto unico | Array `pix[]` (pode ter varios) |

---

## Fase 7 — Ajustes UI Desktop

### 7.1 QR Dialog — Imagem base64

Se `qr_image_base64` existir, exibir a imagem QR renderizada:

```python
if qr_image_base64:
    pixmap = QPixmap()
    pixmap.loadFromData(QByteArray.fromBase64(qr_image_base64.encode()))
    img_label = QLabel()
    img_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio))
```

### 7.2 Dashboard — KPIs

Sem mudanca necessaria. KPIs ja contam por status (PENDENTE, REGISTRADO, etc).
Opcionalmente, adicionar KPI "PIX Pendentes" e "PIX Registrados" no futuro.

---

## Fases de Implementacao (resumo)

### Fase 1 — Config + Schema Oracle (nao quebra nada)
1. Variaveis PIX em `config.py`
2. Migracoes Oracle (colunas + sinonimo PCCOB)
3. Funcoes get/set CONFIGURACOES em `oracle.py`
4. `.env.example`

### Fase 2 — Settings Dialog: Tab Cobranca
5. Criar `cobranca_tab.py` (carregar PCCOB + checkboxes + salvar CONFIGURACOES)
6. Integrar no `settings_dialog.py`

### Fase 3 — Sync PCPREST (modificado)
7. Ler CODCOBs da CONFIGURACOES
8. WHERE CODCOB IN (...), MERGE com MODO_COBRANCA

### Fase 4 — Cliente PIX
9. Criar `pix_client.py` (token dedicado, mTLS, CRUD COBV)

### Fase 5 — Jobs PIX
10. Criar `registrar_pix.py`
11. Criar `consultar_pix.py`
12. Filtrar boleto hibrido em `registrar_boletos.py`
13. Registrar jobs no `scheduler.py`

### Fase 6 — Webhook PIX
14. Criar `pix_webhook_receiver.py`
15. Registrar rota em `api_routes.py`

### Fase 7 — UI + Testes
16. QR Dialog: imagem base64
17. Testar sync com ambos CODCOBs
18. Testar COBV em sandbox
19. Testar webhook PIX
20. Testar retrocompatibilidade (sem CODCOB_PIX configurado)

---

## Resumo de Impacto

| Metrica | Valor |
|---------|-------|
| Arquivos novos | 6 |
| Arquivos modificados | 8 |
| Arquivos intocados | ~27 |
| Linhas novas estimadas | ~900 |
| Risco de quebrar funcionalidade atual | **Zero** (sem CODCOB_PIX = comportamento atual) |
| Tempo estimado de implementacao | 5-7 horas |

---

## Verificacao Final

- [ ] Tab Cobranca carrega PCCOB e exibe lista com checkboxes
- [ ] Selecao salva em CONFIGURACOES e persiste entre sessoes
- [ ] Sync le CODCOBs da CONFIGURACOES e busca ambos os tipos
- [ ] MODO_COBRANCA gravado corretamente no MERGE (baseado em flag PCCOB)
- [ ] Boletos BOLETO_HIBRIDO continuam registrando normalmente
- [ ] PIX COBV cria QR Code com vencimento em sandbox
- [ ] pixCopiaECola salvo no Oracle e exibido no QR Dialog
- [ ] Imagem QR base64 exibida no dialog (endpoint cobv-emv)
- [ ] Webhook PIX recebe notificacao e atualiza status para BAIXADO
- [ ] Consultar_pix detecta pagamentos como fallback do webhook
- [ ] Writeback Oracle funciona (QRCODE_PIX populado na PCPREST)
- [ ] Sem CODCOB_PIX configurado = fluxo PIX desabilitado (retrocompativel)
- [ ] Sem nenhuma CONFIGURACAO = usa WINTHOR_CODCOB do .env (fallback)
- [ ] Nenhum secret hardcoded, logs sem dados sensiveis
