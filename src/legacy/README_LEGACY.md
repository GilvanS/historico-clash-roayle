# Arquivos Legados (SQL/SQLite)

Esta pasta contém scripts que utilizavam SQLite como banco de dados principal.
Eles foram **removidos do pipeline de CI** em **29/04/2026** durante a migração
para a arquitetura 100% CSV.

## Por que foram arquivados?

O projeto utiliza GitHub Actions com runners efêmeros: o banco `.db` era perdido
a cada execução, causando perda de histórico de batalhas. A solução foi migrar
para arquivos CSV acumulativos no repositório Git.

## Scripts arquivados

| Arquivo | Função original |
|---|---|
| `analyzer.py` | Análise de batalhas via queries SQL |
| `check_data.py` | Debug de dados via SQLite em memória compartilhada |
| `db_rehydration.py` | Importação/exportação entre CSV e banco SQLite |
| `fix_missing_battles.py` | Correção pontual de batalhas faltantes no banco |
| `gerar_html_screenshot.py` | Geração de screenshots via SQL |
| `opponents_report.py` | Coleta de batalhas da API e persistência em SQLite |
| `update_readme_from_analytics.py` | Leitura de stats do banco para atualizar README |
| `update_readme_stats.py` | Versão anterior do atualizador de README via SQL |

## Substitutos (arquitetura CSV-First)

| Script legado | Substituto CSV |
|---|---|
| `opponents_report.py` | `src/collect_battles_csv.py` |
| `db_rehydration.py` | Não necessário (CSVs são a fonte da verdade) |
| `analyzer.py` | `src/csv_database_manager.py` + `html_generator.py` |
| `update_readme_from_analytics.py` | `src/update_readme_from_csv.py` |
| `update_readme_stats.py` | `src/update_readme_from_csv.py` |

## Uso manual (se necessário)

Estes scripts ainda podem ser executados localmente se um banco `.db` estiver
disponível, mas **não são chamados pelo GitHub Actions**.

> ⚠️ AVISO: Não adicionar estes arquivos de volta aos workflows de CI.
