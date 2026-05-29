# Configuracao do GitHub Actions para Relatorio de Oponentes

## O que foi criado

Foi criado o workflow `.github/workflows/update-opponents-report.yml` que:

- **Executa automaticamente a cada hora**
- **Salva batalhas no banco de dados** (acumula dados)
- **Gera CSV completo** com todas as batalhas acumuladas
- **Faz commit automatico** dos arquivos gerados
- **Pode ser executado manualmente** via GitHub Actions

## Configuracao Necessaria

### 1. Configurar Secrets no GitHub

O workflow usa os mesmos secrets do workflow principal:

1. Va em: **Settings** → **Secrets and variables** → **Actions**
2. Certifique-se de que existem os seguintes secrets:
   - `CR_API_TOKEN`: Seu token da API do Clash Royale
   - `CR_PLAYER_TAG`: Sua tag de jogador (ex: `#2QR292P`)

### 2. Verificar Permissoes

O workflow precisa de permissao para fazer commit. Isso ja esta configurado no arquivo.

## Arquivos Gerados

O workflow gera e commita automaticamente:

- **`src/oponentes.db`**: Banco de dados SQLite com todas as batalhas acumuladas
- **`src/oponentes_todos.csv`**: CSV completo com todas as batalhas do banco
- **`src/oponentes_2025.csv`**: CSV do ano atual (ou ano especificado)

## Como Funciona

1. **A cada hora** (cron: `0 * * * *`):
   - Busca novas batalhas da API
   - Salva no banco de dados (evita duplicatas)
   - Gera CSV completo do banco
   - Faz commit dos arquivos atualizados

2. **Execucao manual**:
   - Va em **Actions** → **Update Opponents Report** → **Run workflow**

3. **No push para main**:
   - Executa automaticamente (util para testes)

## Verificar Execucao

1. Va em **Actions** no GitHub
2. Clique em **Update Opponents Report**
3. Veja os logs de execucao
4. Verifique os commits automaticos no historico

## Personalizacao

### Mudar Frequencia

Edite o arquivo `.github/workflows/update-opponents-report.yml`:

```yaml
schedule:
  - cron: '0 * * * *'  # A cada hora
  # - cron: '*/30 * * * *'  # A cada 30 minutos
  # - cron: '0 */6 * * *'   # A cada 6 horas
```

### Adicionar Mais Anos

Para gerar CSV de outros anos, adicione no workflow:

```yaml
- name: Generate CSV for specific year
  run: |
    cd src
    python opponents_report.py --do-banco --ano 2024 --token "$CR_API_TOKEN" --tag "$CR_PLAYER_TAG"
```

## Troubleshooting

### Workflow nao executa automaticamente

- Verifique se os secrets estao configurados
- Verifique se o workflow esta no branch `main`
- GitHub Actions pode ter delay de ate 5 minutos

### Erro de permissao

- Verifique se o workflow tem permissao `contents: write`
- Verifique se o token tem permissao para fazer push

### Nenhum commit sendo feito

- Isso e normal se nao houver novas batalhas
- O workflow so commita se houver mudancas

## Exemplo de Execucao

```
Run 1 (00:00): 30 batalhas novas → commit
Run 2 (01:00): 5 batalhas novas → commit
Run 3 (02:00): 0 batalhas novas → sem commit
Run 4 (03:00): 12 batalhas novas → commit
...
```

Apos alguns dias, voce tera centenas ou milhares de batalhas acumuladas no banco de dados!

