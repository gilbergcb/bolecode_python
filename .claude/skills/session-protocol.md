# Skill: Session Protocol

## Início de Sessão
1. Ler `memory/wake-up.md` do Obsidian
2. Verificar `memory/inbox.md` por tasks pendentes
3. Checar se existe journal de ontem para continuidade
4. Resumir: estado atual + pendências + prioridade sugerida

## Durante a Sessão
- Decisão arquitetural importante → criar `decisions/DEC-NNNN-slug.md`
- Contexto ficando grande → offload para Obsidian (PUT na nota relevante)
- Bug resolvido com insight não-óbvio → anotar em `project-context/`
- Nova task surgiu → adicionar em `memory/inbox.md`

## Fim de Sessão
1. Criar/atualizar `memory/journal/YYYY-MM-DD.md`:
   - O que foi feito
   - Decisões tomadas
   - O que ficou pendente
2. Atualizar `memory/wake-up.md`:
   - Estado atual do projeto
   - Pendências atualizadas
   - Avisos para próxima sessão
3. Limpar items concluídos do `memory/inbox.md`

## Formato Journal
```markdown
# Journal - YYYY-MM-DD
## Sessão N
### Feito
- item 1
### Decisões
- DEC-NNNN: resumo
### Pendente
- item para próxima sessão
```
