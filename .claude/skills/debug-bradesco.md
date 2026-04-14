# Skill: Debug API Bradesco

## Diagnóstico Rápido por Erro

### 401 Unauthorized
1. Token expirado? Checar `_token_cache` em `src/api/bradesco_client.py`
2. Cert mTLS válido? `openssl x509 -in certs/cert.pem -text -noout`
3. client_id/secret corretos? Verificar `.env`
4. Sandbox vs produção? Checar `BRADESCO_ENV`

### 400 Bad Request
1. Campos obrigatórios preenchidos? (nosso_numero, valor, vencimento, pagador)
2. Valor em centavos sem decimal? R$50.00 → "5000"
3. Data formato YYYY-MM-DD? (não DD/MM/YYYY)
4. CNPJ com 14 dígitos? (8 raiz + 4 filial + 2 dígito)

### 409 Conflict
- Boleto já registrado com mesmo nosso_numero
- Verificar idempotência: ON CONFLICT no PG

### 500 / Timeout
1. Bradesco fora? Verificar status
2. Retry ativo? Tenacity com backoff exponencial
3. Logar request_id para suporte

### SSL Error
1. Chain completa? `openssl s_client -connect api.bradesco.com.br:443`
2. CN do cert = razao_social + CNPJ?
3. RSA 2048+ ou ECDSA P-256?

## Referência Completa
Para mapeamento de campos e detalhes: ler `project-context/api-bradesco` no Obsidian.
