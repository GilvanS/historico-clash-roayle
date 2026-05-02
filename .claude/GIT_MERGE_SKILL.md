# 🚀 Skill: Git Merge Mastery - Evitar Problemas de Merge

## Objetivo
Prevenir e resolver problemas comuns de git merge, especialmente com GitHub Pages.

## Problemas Comuns Identificados
1. **Merge incompleto** - Commits da feature branch não chegam no main
2. **Cache do GitHub Pages** - HTML antigo persiste mesmo após updates
3. **Conflitos de arquivos binários** - HTML/CSS com conflitos complexos
4. **Rebase travado** - Git em estado inconsistent

## 📋 Protocolo de Merge Seguro

### 1. PRÉ-MERGE (Preparação)
```bash
# Verificar diferenças entre branches
git diff main..feature/nova-feature --name-only

# Verificar histórico
git log --oneline --graph --all --decorate -10

# Ensure clean working directory
git status
git checkout .
```

### 2. MERGE CORRETO (Passo a passo)
```bash
# 1. Atualizar main
git checkout main
git pull origin main

# 2. Fazer merge explícito
git merge feature/nova-feature --no-ff -m "feat: merge completo de feature/nova-feature"

# 3. Verificar conflitos
git status

# 4. Resolver conflitos se necessário
git checkout --theirs arquivo-conflitante.html
git add arquivo-conflitante.html

# 5. Finalizar merge
git commit -m "resolve: conflitos do merge"
```

### 3. PÓS-MERGE (Validação)
```bash
# Verificar se TODOS os commits chegaram
git log --oneline -5

# Verificar arquivos específicos
git show HEAD --name-only

# Testar localmente antes do push
python -m http.server 8000  # Verificar se funciona
```

## 🎯 Solução Para GitHub Pages Cache

### Quando o GitHub Pages não atualiza:
```bash
# 1. Mudar nome do arquivo principal (FORÇA rebuild)
mv docs/index.html docs/dashboard-NOVO.html

# 2. Criar redirect simples
echo "<!DOCTYPE html><html><head><meta http-equiv='refresh' content='0; URL=./dashboard-NOVO.html'></head><body>Redirecting...</body></html>" > docs/index.html

# 3. Commit e push
git add docs/index.html docs/dashboard-NOVO.html
git commit -m "fix: força rebuild GitHub Pages com redirect"
git push

# 4. Após 5min, restaurar nome original
mv docs/dashboard-NOVO.html docs/index.html
git add docs/index.html
git commit -m "fix: restaura nome original após rebuild"
git push
```

## 🔧 Troubleshooting de Estados Travados

### Git em rebase/interactive mode:
```bash
# Abortar rebase
git rebase --abort

# Resetar para estado limpo
git reset --hard origin/main

# Remover locks se necessário
rm -f .git/index.lock
```

### Processos git travados (Windows):
```bash
# Matar processos git
taskkill /f /im git*

taskkill /f /im GitHubDesktop.exe
```

## 📊 Verificação de Sucesso

### Após merge, verificar:
1. ✅ GitHub Actions passando
2. ✅ GitHub Pages atualizado (aguardar 2-5min)  
3. ✅ Testar URL atual com Ctrl+Shift+R (hard refresh)
4. ✅ Confirmar que todos os arquivos da feature estão no main

## ⚠️ Checklists de Segurança

### ANTES de fazer merge:
- [ ] Backup dos arquivos importantes
- [ ] Verificar diferenças entre branches
- [ ] Testar feature branch localmente
- [ ] Coordenar com time se aplicável

### APÓS merge:
- [ ] Verificar se build passa
- [ ] Testar produção
- [ ] Documentar mudanças
- [ ] Informar stakeholders

## 🚨 Casos Especiais

### Merge de grandes refactors:
```bash
# Fazer merge gradual
git merge feature/refactor --no-commit
# Verificar arquivo por arquivo
git status
git diff --cached
# Commit apenas quando confirmado
git commit -m "feat: merge seguro de refactor grande"
```

### Rollback seguro:
```bash
# Reverter merge específico
git revert -m 1 MERGE_COMMIT_HASH

# Ou reset hard (cuidado!)
git reset --hard COMMIT_ANTERIOR
```

---

**Lembrete:** Sempre prefira `merge --no-ff` para manter histórico claro e evitar problemas com GitHub Pages!