# Guia de CSVs por Periodo (Dia, Semana, Mes, Ano)

## Como Funciona

O script gera **4 CSVs diferentes** baseados no banco de dados acumulado:

1. **Dia atual**: `oponentes_dia_YYYYMMDD.csv`
2. **Semana atual**: `oponentes_semana_YYYYWW.csv` (segunda a domingo)
3. **Mes atual**: `oponentes_mes_YYYYMM.csv`
4. **Ano atual**: `oponentes_ano_YYYY.csv`

## Acumulacao Automatica

Como todos os dados estao no banco de dados (`oponentes.db`), a acumulacao acontece automaticamente:

- **CSV do dia**: Contem apenas batalhas do dia atual
- **CSV da semana**: Contem TODAS as batalhas da semana (inclui todos os dias da semana)
- **CSV do mes**: Contem TODAS as batalhas do mes (inclui todas as semanas do mes)
- **CSV do ano**: Contem TODAS as batalhas do ano (inclui todos os meses do ano)

### Exemplo Pratico

**Dia 11/12/2025:**
- `oponentes_dia_20251211.csv` → 11 batalhas do dia 11
- `oponentes_semana_202549.csv` → 27 batalhas (todos os dias da semana, incluindo dia 11)
- `oponentes_mes_202512.csv` → 27 batalhas (todos os dias de dezembro ate agora)
- `oponentes_ano_2025.csv` → 27 batalhas (todos os dias de 2025 ate agora)

**Quando o dia 11 acaba e comeca o dia 12:**
- `oponentes_dia_20251212.csv` → Novas batalhas do dia 12
- `oponentes_semana_202549.csv` → Atualizado com batalhas do dia 12 (inclui dia 11 tambem)
- `oponentes_mes_202512.csv` → Atualizado com batalhas do dia 12
- `oponentes_ano_2025.csv` → Atualizado com batalhas do dia 12

**Nao ha sobrescrita!** Os CSVs sao sempre gerados do banco completo, entao:
- Quando o dia acaba, os dados ja estao no CSV da semana
- Quando a semana acaba, os dados ja estao no CSV do mes
- Quando o mes acaba, os dados ja estao no CSV do ano

## Como Usar

### No GitHub Actions (Automatico)

O workflow executa a cada 30 minutos e:
1. Busca novas batalhas da API
2. Salva no banco de dados
3. Gera os 4 CSVs (dia, semana, mes, ano)
4. Faz commit automatico

### Localmente

```powershell
cd src
python opponents_report.py --periodos --token "SEU_TOKEN" --tag "#SUATAG"
```

## Estrutura dos Arquivos

```
src/
├── oponentes.db                    # Banco de dados (fonte unica)
├── oponentes_dia_20251211.csv     # Batalhas do dia 11/12/2025
├── oponentes_semana_202549.csv    # Batalhas da semana 49 de 2025
├── oponentes_mes_202512.csv       # Batalhas de dezembro/2025
└── oponentes_ano_2025.csv          # Batalhas de 2025
```

## Nomenclatura dos Arquivos

- **Dia**: `oponentes_dia_YYYYMMDD.csv` (ex: `oponentes_dia_20251211.csv`)
- **Semana**: `oponentes_semana_YYYYWW.csv` (ex: `oponentes_semana_202549.csv`)
- **Mes**: `oponentes_mes_YYYYMM.csv` (ex: `oponentes_mes_202512.csv`)
- **Ano**: `oponentes_ano_YYYY.csv` (ex: `oponentes_ano_2025.csv`)

## Download dos Arquivos

Os arquivos ficam no repositorio GitHub na pasta `src/`:

1. Acesse seu repositorio no GitHub
2. Va na pasta `src/`
3. Clique no arquivo desejado
4. Clique em "Download" ou "Raw"

## Observacoes Importantes

1. **Nao ha sobrescrita**: Os CSVs sao sempre gerados do banco completo
2. **Acumulacao automatica**: Dados do dia vao para semana, semana para mes, mes para ano
3. **Frequencia**: GitHub Actions executa a cada 30 minutos
4. **Banco e fonte unica**: Todos os CSVs sao gerados do mesmo banco de dados

## Exemplo de Evolucao

**Dia 1:**
- Dia: 10 batalhas
- Semana: 10 batalhas
- Mes: 10 batalhas
- Ano: 10 batalhas

**Dia 2:**
- Dia: 15 batalhas (novo dia)
- Semana: 25 batalhas (dia 1 + dia 2)
- Mes: 25 batalhas
- Ano: 25 batalhas

**Dia 8 (nova semana):**
- Dia: 12 batalhas
- Semana: 12 batalhas (nova semana, so dia 8)
- Mes: 37 batalhas (semana 1 + semana 2)
- Ano: 37 batalhas

E assim por diante!

