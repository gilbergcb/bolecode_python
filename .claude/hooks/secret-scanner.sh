#!/bin/bash
# Hook: Secret Scanner (PreToolUse)
# Bloqueia escrita de código contendo secrets hardcoded
# Exit 2 = bloqueia Claude | Exit 0 = permite

# Lê o input do hook via stdin
INPUT=$(cat)

# Patterns de secrets (grep -iE, regex estendida — compatível Git Bash Windows)
FOUND=$(echo "$INPUT" | grep -iE \
  'password\s*=\s*["\x27].{4,}|secret\s*=\s*["\x27].{4,}|api_key\s*=\s*["\x27].{4,}|-----BEGIN.*(PRIVATE KEY|CERTIFICATE)-----|sk-[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36}|client_secret\s*=\s*["\x27].{8,}' \
  2>/dev/null)

if [ -n "$FOUND" ]; then
  echo "BLOQUEADO: Secret detectado no conteudo!"
  echo ""
  echo "Encontrado:"
  echo "$FOUND" | head -5
  echo ""
  echo "Use variaveis de ambiente (.env) ao inves de hardcoded secrets."
  exit 2
fi

exit 0
