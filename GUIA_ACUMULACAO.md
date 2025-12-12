# Guia de Acumulacao de Batalhas

## Como Funciona

O script agora suporta **acumulacao de dados** usando banco de dados SQLite. Isso permite:

1. **Executar a cada hora** sem perder dados
2. **Evitar duplicatas** automaticamente
3. **Gerar CSV acumulado** com todas as batalhas coletadas
4. **Incluir informacoes do deck** usado em cada batalha

## Como Usar

### 1. Primeira Execucao (Salvar no Banco)

```powershell
python opponents_report.py --salvar-banco --token "SEU_TOKEN" --tag "#SUATAG"
```

Isso vai:
- Buscar batalhas da API
- Salvar no banco de dados (`oponentes.db`)
- Gerar CSV com as batalhas atuais

### 2. Execucoes Subsequentes (A Cada Hora)

Execute o mesmo comando novamente:

```powershell
python opponents_report.py --salvar-banco --token "SEU_TOKEN" --tag "#SUATAG"
```

O script vai:
- Buscar novas batalhas da API
- Adicionar apenas as novas ao banco (ignora duplicatas)
- Gerar CSV atualizado

### 3. Gerar CSV Acumulado do Banco

Para gerar CSV com TODAS as batalhas acumuladas no banco:

```powershell
python opponents_report.py --do-banco --todos --token "SEU_TOKEN" --tag "#SUATAG"
```

Ou para um ano especifico:

```powershell
python opponents_report.py --do-banco --ano 2025 --token "SEU_TOKEN" --tag "#SUATAG"
```

## Estrutura do CSV Gerado

O CSV agora inclui:

- **deck_jogador**: Cartas do seu deck (separadas por `|`)
- **deck_oponente**: Cartas do deck do oponente (separadas por `|`)
- Todas as outras colunas anteriores

Exemplo:
```
deck_jogador: Barbarian Barrel | Bats | Dart Goblin | Goblin Gang | Lightning | Musketeer | Royal Recruits | Skeleton Barrel
deck_oponente: Cannon | Ice Spirit | Knight | Musketeer | Poison | Royal Hogs | Skeletons | The Log
```

## Quantas Batalhas Conseguir Acumular?

### Por Execucao
- **API retorna**: ~25-30 batalhas (fixo)
- **Periodo coberto**: Depende de quantas batalhas voce joga

### Acumulacao ao Longo do Tempo

| Frequencia | Batalhas por Dia | Batalhas por Semana | Batalhas por Mes |
|------------|------------------|---------------------|------------------|
| **A cada hora** | ~720 batalhas* | ~5.040 batalhas* | ~21.600 batalhas* |
| **A cada 6 horas** | ~120 batalhas* | ~840 batalhas* | ~3.600 batalhas* |
| **Diariamente** | ~30 batalhas | ~210 batalhas | ~900 batalhas |

*Teorico - depende de quantas batalhas voce realmente joga. A API so retorna as ultimas 25-30, entao se voce joga 50 batalhas por hora, so as ultimas 25-30 serao capturadas.

## Recomendacao

Para maximizar a cobertura:

1. **Execute a cada hora** durante o dia
2. Use `--salvar-banco` para acumular dados
3. Periodicamente gere CSV completo com `--do-banco --todos`

## Exemplo de Automatizacao (Windows Task Scheduler)

1. Abra o Agendador de Tarefas
2. Crie uma nova tarefa
3. Configure para executar a cada hora:
   ```
   python A:\Workspace\clash-royale-history\src\opponents_report.py --salvar-banco --token "SEU_TOKEN" --tag "#SUATAG"
   ```

## Arquivos Gerados

- **oponentes.db**: Banco de dados SQLite com todas as batalhas acumuladas
- **oponentes_2025.csv**: CSV do ano atual (gerado a cada execucao)
- **oponentes_todos.csv**: CSV completo (quando usar `--do-banco --todos`)

## Observacoes Importantes

1. **Duplicatas sao evitadas automaticamente** usando `player_tag + battle_time + tag_oponente` como chave unica
2. **O banco cresce continuamente** - nao ha limite teorico de batalhas
3. **Execute regularmente** para nao perder batalhas antigas (a API so retorna as ultimas 25-30)

