# Anti-Conflito: Seleção de Contas Multi-Conta

## Problema Recorrente
⚠️ **ALERTA**: Toda vez que o `html_generator.py` é modificado, a seleção de contas pode quebrar.

**Sintomas:**
- Ao trocar de conta (CONTA PRINCIPAL ↔ CONTA SECUNDÁRIA), nada acontece
- O conteúdo não atualiza ao clicar nas tabs
- Erro no console: "ERRO CRÍTICO: Container de conta não encontrado no DOM"

---

## Arquitetura Sensível (NÃO MODIFICAR SEM NECESSIDADE)

### HTML Estrutura Multi-Conta
```html
<!-- TABS DE SELEÇÃO (line ~1833 no index.html) -->
<div class="cr-account-tabs">
    <div class="cr-tab active" onclick="switchAccountTab('#2QR292P', this)">CONTA PRINCIPAL</div>
    <div class="cr-tab" onclick="switchAccountTab('#2220UQQ0UU', this)">CONTA SECUNDÁRIA</div>
</div>

<!-- CONTEÚDO POR CONTA -->
<div class="cr-dashboard-content">
    <div id="account-tab-2QR292P" class="cr-tab-content active">...</div>
    <div id="account-tab-2220UQQ0UU" class="cr-tab-content">...</div>
</div>
```

### Funções JavaScript Críticas (NÃO ALTERAR A MENOS QUE SEJA NECESSÁRIO)
1. `switchAccountTab(tag, element)` - Line ~2818
   - **NÃO REMOVER** a manipulação de `localStorage` para `cr_inner_tab_*`
   - **NÃO REMOVER** o `dispatchEvent` para restaurar abas internas
   - **MANTENHA** o seletor `.cr-dashboard-content > .cr-tab-content`

2. `switchInnerTab(event, targetId)` - Line ~2887
   - **NÃO ALTERAR** o formato de `onclick="switchInnerTab(event, 'tab-id')"`

---

## Regras de Ouro ao Editar html_generator.py

### ✅ FAZER
1. Mantenha o `id="account-tab-{clean_tag}"` para cada conta
2. Mantenha `class="cr-tab-content {active_class}"` 
3. Mantenha `class="cr-account-tabs"` para o container de tabs
4. Preserve o `onclick="switchAccountTab('{tag}', this)"` nos elementos de tab
5. Preserve o `onclick="switchInnerTab(event, '{targetId}')"` nas abas internas

### ❌ NÃO FAZER
1. **NUNCA** remova ou renomeie classes CSS `.cr-dashboard-content`, `.cr-tab-content`
2. **NUNCA** remova o `id="account-tab-*"` dos containers de conta
3. **NUNCA** altere os seletores no JavaScript `switchAccountTab()`
4. **NUNCA** adicione breakpoints ou `debugger` no código de tabs
5. **NUNCA** remova `load_dotenv()` - é necessário para ler CR_PLAYER_TAG_SEC

---

## Como Verificar se Não Quebrou

### 1. Verifique no index.html gerado
```bash
# Procura se ambas contas estão no HTML
grep "account-tab-2QR292P" index.html
grep "account-tab-2220UQQ0UU" index.html

# Se encontrar APENAS uma, o problema é no tracked_tags
```

### 2. Verifique se o JavaScript está intacto
```bash
grep "switchAccountTab" index.html
# Deve encontrar pelo menos 2 ocorrências
```

### 3. Teste manual local
```bash
# Gere o HTML localmente
cd src
python html_generator.py

# Abra index.html no navegador
# Teste: clique em cada tab de conta
# Deveria trocar o conteúdo sem erros no console
```

---

## Se Quebrou - Como Corrigir Rápido

### Causa 1: `CR_PLAYER_TAG_SEC` não está sendo lida
```python
# Verifique se load_dotenv() está presente no topo
from dotenv import load_dotenv
load_dotenv()

# Verifique se tracked_tags tem 2 elementos
print(self.tracked_tags)  # Deve mostrar ['#2QR292P', '#2220UQQ0UU']
```

### Causa 2: IDs das contas não batem
```python
# O ID no HTML deve ser clean_tag (sem #)
clean_tag = tag.replace('#', '')  # '#2QR292P' -> '2QR292P'
# HTML: <div id="account-tab-2QR292P">
```

### Causa 3: JavaScript selector quebrado
```javascript
// Este seletor deve funcionar SEMPRE:
const allContents = document.querySelectorAll('.cr-dashboard-content > .cr-tab-content');
```

---

## Checklist Antes de Commit

- [ ] `load_dotenv()` está presente no início do arquivo
- [ ] `CR_PLAYER_TAG_SEC` está sendo lida corretamente
- [ ] `tracked_tags` contém ambas as contas
- [ ] IDs no HTML estão corretos (`account-tab-{clean_tag}`)
- [ ] JavaScript `switchAccountTab` não foi modificado
- [ ] Testou localmente a troca de contas

---

## Arquivos Importantes

| Arquivo | Linha | Importância |
|---------|-------|-------------|
| `src/html_generator.py` | ~4373-4399 | Gera as tabs e containers |
| `src/html_generator.py` | ~2815-2884 | switchAccountTab JS |
| `index.html` | ~1833 | Tabs HTML |
| `index.html` | ~1852-1853 | Container conteúdo |

---

## CSV Encoding - Regras para não perder dados

⚠️ **CRÍTICO**: O arquivo `oponentes_ano_2026.csv` DEVE manter a coluna `player_tag` para identificar de qual conta é cada batalha.

### Estrutura correta do CSV
```csv
player_tag;data;nome_oponente;tag_oponente;...;deck_jogador;deck_oponente;...
#2QR292P;14/05/2026 12:41;HUGO;#VC8VC02L8;...;Giant | Hogs | ...;Arrows | ...;...
#2220UQQ0UU;14/05/2026 12:40;Opponent2;#TAG;...;Deck;Deck;...
```

### Encodings suportados
O código tenta detectar o encoding na seguinte ordem:
1. `utf-8-sig` (com BOM) - **PREFERIDO**
2. `utf-8`
3. `utf-16-le`
4. `latin1`
5. `cp1252`

### Coluna essencial: `player_tag`
- **SEMPRE** deve existir no CSV
- Identifica qual conta (#2QR292P ou #2220UQQ0UU) fez a batalha
- Sem esta coluna, o dashboard não consegue separar os dados por conta

### Scripts que escrevem no CSV
1. `collect_battles_csv.py` - Coleta da API e adiciona `player_tag`
2. `sanitize_csvs.py` - NÃO deve remover a coluna `player_tag`
3. `deduplicate_csvs.py` - NÃO deve remover a coluna `player_tag`

### Validação local
```bash
cd src
python -c "
from html_generator import GitHubPagesHTMLGenerator
gen = GitHubPagesHTMLGenerator()
print('Battles by tag:', {k: len(v) for k, v in gen.battles_by_tag.items()})
"
# Deve mostrar:
# Battles by tag: {'#2QR292P': X, '#2220UQQ0UU': Y}
```

---

## Logs de Debug

Se a troca de contas não funcionar, verifique o console do navegador:
```javascript
// Procure por estas mensagens:
'Solicitando troca para conta: #2QR292P'
'Conteúdo da conta ativado com sucesso: account-tab-2QR292P'
'ERRO CRÍTICO: Container de conta não encontrado no DOM'
```

Se ver o erro, o problema é que:
1. O ID do container HTML não existe, ou
2. O `tracked_tags` só tem 1 conta

---

_Last updated: 2026-05-15_