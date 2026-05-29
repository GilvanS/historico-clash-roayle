# Como Configurar Token e Tag

Existem **duas formas** de configurar seu token e tag:

## Opção 1: Direto na linha de comando (Mais Simples) ⭐

Execute o script passando o token e tag diretamente:

**Com Python diretamente (recomendado):**
```bash
cd src
python opponents_report.py --token "SEU_TOKEN_AQUI" --tag "#SUATAG"
```

**Ou com uv (se tiver instalado):**
```bash
cd src
uv run python opponents_report.py --token "SEU_TOKEN_AQUI" --tag "#SUATAG"
```

**Exemplo real:**
```bash
python opponents_report.py --token "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." --tag "#YVJR0JLY"
```

---

## Opção 2: Variáveis de Ambiente (Recomendado para uso frequente)

Configure uma vez e use sempre:

### No Windows (PowerShell):
```powershell
$env:CR_API_TOKEN="seu_token_aqui"
$env:CR_PLAYER_TAG="#SUATAG"
```

Depois execute normalmente:
```bash
cd src
python opponents_report.py
```

### No Windows (CMD):
```cmd
set CR_API_TOKEN=seu_token_aqui
set CR_PLAYER_TAG=#SUATAG
```

Depois execute normalmente:
```bash
cd src
python opponents_report.py
```

### No Linux/Mac:
```bash
export CR_API_TOKEN="seu_token_aqui"
export CR_PLAYER_TAG="#SUATAG"
```

Depois execute normalmente:
```bash
cd src
python opponents_report.py
```

---

## Onde obter o Token?

1. Acesse: https://developer.clashroyale.com
2. Faça login com sua conta Supercell
3. Clique em "Create New Key" ou "My Keys"
4. Copie o token gerado
5. Use no script (com ou sem aspas)

## Como descobrir sua Tag?

Sua tag do jogador aparece no perfil do Clash Royale:
- No jogo: Perfil → Tag do jogador (exemplo: #YVJR0JLY)
- No site: https://royaleapi.com (procure por seu nome)

**IMPORTANTE:** A tag sempre começa com `#` e deve ser incluída!

---

## Exemplo Completo

```bash
# Opção 1: Direto na linha de comando
cd src
python opponents_report.py --token "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0YWciOiJZ..." --tag "#YVJR0JLY"

# Opção 2: Variáveis de ambiente (PowerShell)
$env:CR_API_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0YWciOiJZ..."
$env:CR_PLAYER_TAG="#YVJR0JLY"
cd src
python opponents_report.py
```

---

## Dica: Criar um arquivo .bat (Windows)

Crie um arquivo `executar.bat` na pasta `src`:

```batch
@echo off
set CR_API_TOKEN=seu_token_aqui
set CR_PLAYER_TAG=#SUATAG
uv run python opponents_report.py
pause
```

Depois é só dar duplo clique no arquivo para executar!

