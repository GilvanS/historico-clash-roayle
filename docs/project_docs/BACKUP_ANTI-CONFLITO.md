# Backup de Alterações - Anti-Conflito Actions

## Contexto
Este projeto usa GitHub Actions que sincroniza dados do Clash Royale automaticamente a cada 30 minutos. Isso pode sobrescrever trabalho local durante desenvolvimento.

## Solução Implementada (Commit: f2e920ccb)

### 1. Script toggle_actions.sh
Local: `./toggle_actions.sh`

Comandos:
- `./toggle_actions.sh pause` - Pausa sincronização automática
- `./toggle_actions.sh resume` - Retoma sincronização automática  
- `./toggle_actions.sh status` - Verifica status

### 2. Workflow mejorado
Arquivo: `.github/workflows/clash-royale-sync.yml`

Adicionada verificação:
```yaml
if [ -f .actions_paused ]; then
  echo "⏸️ Trabalho em progresso detectado. Pulando sincronização automática."
  exit 0
fi
```

### 3. Flag .actions_paused
Quando o script `pause` é executado, cria um arquivo `.actions_paused` que o workflow verifica antes de sincronizar.

## Para Reverter (se necessário)

### Reverter para o workflow antigo:
```bash
git show f2e920ccb~1:.github/workflows/clash-royale-sync.yml > .github/workflows/clash-royale-sync.yml
```

### Remover script e flag:
```bash
rm toggle_actions.sh .actions_paused
```

### Versão anterior do AGENTS.md:
```bash
git show f2e920ccb~1:AGENTS.md > AGENTS_backup_old.md
```

## Commit Original
- Hash: `f2e920ccb`
- Mensagem: "feat: adiciona controle de pausa para Actions e melhora workflow anti-conflito"
- Data: 2026-05-14

---

## Histórico de Commits Relacionados

| Commit | Descrição |
|--------|-----------|
| `f2e920ccb` | Adiciona controle de pausa para Actions |
| `90b2429b3` | chore: sincronização automática (último antes do fix) |
| `c2a1c2383` | Merge branch 'main' (backup antes do pull) |