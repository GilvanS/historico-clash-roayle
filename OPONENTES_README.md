# Relatorio de Oponentes - Clash Royale

Script para gerar relatorio CSV dos oponentes enfrentados durante o ano e identificar repeticoes.

## Como usar

### 1. Configurar variaveis de ambiente

No Windows (PowerShell):
```powershell
$env:CR_API_TOKEN="seu_token_aqui"
$env:CR_PLAYER_TAG="#SUATAG"
```

No Windows (CMD):
```cmd
set CR_API_TOKEN=seu_token_aqui
set CR_PLAYER_TAG=#SUATAG
```

No Linux/Mac:
```bash
export CR_API_TOKEN="seu_token_aqui"
export CR_PLAYER_TAG="#SUATAG"
```

### 2. Executar o script

**Uso basico (ano atual):**
```bash
cd src
uv run python opponents_report.py
```

**Especificar ano:**
```bash
uv run python opponents_report.py --ano 2023
```

**Especificar nome do arquivo:**
```bash
uv run python opponents_report.py --arquivo meus_oponentes.csv
```

**Passar token e tag diretamente:**
```bash
uv run python opponents_report.py --token "seu_token" --tag "#SUATAG"
```

**Ver todas as opcoes:**
```bash
uv run python opponents_report.py --help
```

Ou se estiver usando Python diretamente:
```bash
cd src
python opponents_report.py
```

### 3. Resultado

O script vai gerar um arquivo CSV chamado `oponentes_2024.csv` (ou o ano atual) com todas as informacoes dos oponentes enfrentados.

## Onde obter o token da API

1. Acesse: https://developer.clashroyale.com
2. Faca login com sua conta Supercell
3. Crie um novo token de API
4. Copie o token e use na variavel de ambiente

## Estrutura do CSV gerado

O arquivo CSV contem as seguintes colunas:

- **data**: Data e hora da batalha
- **nome_oponente**: Nome do oponente
- **tag_oponente**: Tag unica do oponente
- **nivel_oponente**: Nivel do oponente
- **trofes_oponente**: Trofeus do oponente na batalha
- **clan_oponente**: Nome do cla do oponente
- **resultado**: Vitoria, Derrota ou Empate
- **coroas_jogador**: Coroas que voce fez
- **coroas_oponente**: Coroas que o oponente fez
- **mudanca_trofes**: Mudanca de trofeus apos a batalha
- **modo_jogo**: Modo de jogo (Ladder, Tournament, etc)
- **tipo_batalha**: Tipo da batalha
- **arena**: Arena onde ocorreu a batalha
- **vezes_enfrentado**: Quantas vezes enfrentou esse oponente no ano

## Identificacao de repeticoes

O script identifica automaticamente se voce enfrentou algum oponente mais de uma vez durante o ano e mostra um resumo no final da execucao.

## Observacoes

- A API do Clash Royale retorna apenas as ultimas ~25 batalhas
- Se voce quiser um historico completo, precisa executar o script regularmente
- O script filtra automaticamente as batalhas do ano atual

