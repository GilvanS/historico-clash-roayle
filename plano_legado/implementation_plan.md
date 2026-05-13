# Plano de Implementação: Integração Multi-Conta e Dashboard com Abas

Este plano visa estabilizar a extração de dados para a conta secundária e refatorar o Dashboard para permitir a visualização alternada entre a conta Principal e Secundária usando um sistema de abas.

## User Review Required

> [!IMPORTANT]
> A extração 30/30 min via GitHub Actions já está configurada para ambas as contas. O sucesso da extração depende apenas dos Segredos (Secrets) `CR_PLAYER_TAG` e `CR_PLAYER_TAG_SEC` estarem corretos no GitHub.

> [!NOTE]
> O Dashboard passará a ter abas para "Batalhas Recentes" e "Deck da Semana", permitindo alternar entre as contas sem recarregar a página.

## Proposed Changes

### [Backend] Coleta e Processamento de Dados

#### [MODIFY] [collect_battles_csv.py](file:///a:/Workspace/historico-clash-roayle/src/collect_battles_csv.py)
* Garantir que a lógica de detecção de múltiplas contas seja resiliente a espaços e formatos de tag (já iniciado, mas farei uma revisão final).

#### [MODIFY] [html_generator.py](file:///a:/Workspace/historico-clash-roayle/src/html_generator.py)
* **Multi-Account Loading**: Refatorar o `__init__` para carregar todas as tags de conta disponíveis.
* **Separated Data Caches**: Manter caches de batalhas e métricas separados por conta.
* **Tabbed UI Generation**: Atualizar `generate_dashboard_html` para injetar o HTML das abas e os containers de conteúdo específicos de cada conta.

#### [MODIFY] [member_generator.py](file:///a:/Workspace/historico-clash-roayle/src/member_generator.py)
* Forçar a geração da página de perfil individual para a conta secundária, mesmo que ela não esteja no clã (`clan_members.csv`).

### [Frontend] Dashboard e Visualização

#### [MODIFY] [index.html](file:///a:/Workspace/historico-clash-roayle/index.html) (via html_generator.py)
* Implementar o sistema de abas "Principal" vs "Secundária" nas seções:
    * Resumo de Status (Mini cards superiores).
    * Deck da Semana.
    * Relatório de Batalhas Recentes.

## Verification Plan

### Automated Tests
* Executar `python src/collect_battles_csv.py` para validar a coleta multi-conta localmente.
* Executar `python src/html_generator.py` para gerar o dashboard e verificar a estrutura das abas.

### Manual Verification
* Abrir `index.html` e testar a alternância entre as abas.
* Verificar se a página de perfil da conta secundária foi gerada corretamente (ex: `member_nome_da_conta.html`).
