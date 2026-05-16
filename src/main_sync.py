#!/usr/bin/env python3
"""
Mestre da Sincronização Clash Royale (30 MIN)
Orquestra: Coleta -> Consolidação -> README -> Dashboard HTML
"""

import os
import sys
import logging
from datetime import datetime

# Adiciona o diretório src ao path se necessário
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from collect_battles_csv import main as collect_main
from update_readme_from_csv import ReadmeCSVUpdater
from html_generator import GitHubPagesHTMLGenerator
from clan_generator import ClanAnalyticsGenerator
from member_generator import MemberPageGenerator

def main():
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    # Carrega variaveis de ambiente de forma robusta (raiz do projeto)
    from dotenv import load_dotenv
    src_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(src_dir)
    dotenv_path = os.path.join(project_root, '.env')
    
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        logger.info(f"OK: Arquivo .env carregado de: {dotenv_path}")
    else:
        logger.warning(f"AVISO: Arquivo .env nao encontrado em: {dotenv_path}")

    logger.info("=" * 60)
    logger.info("INICIANDO SINCRONIZACAO CLASH ROYALE (PIPELINE UNICO)")
    logger.info("=" * 60)
    
    # Debug de Tags
    tag_pri = os.environ.get("CR_PLAYER_TAG")
    tag_sec = os.environ.get("CR_PLAYER_TAG_SEC")
    logger.info(f"Tags detectadas: Principal={tag_pri}, Secundaria={tag_sec}")

    
    # Validação de Integridade (Segurança para o Dashboard Multi-Conta)
    # Se estiver no GitHub Actions, a tag secundária é OBRIGATÓRIA para evitar regressão do UI.
    is_github = os.environ.get("GITHUB_ACTIONS") == "true"
    player_tag_sec = os.environ.get("CR_PLAYER_TAG_SEC")
    
    if is_github and not player_tag_sec:
        logger.error("❌ ERRO CRÍTICO: A variável CR_PLAYER_TAG_SEC não foi encontrada!")
        logger.error("Para evitar que o dashboard seja sobrescrito no formato de conta única, o pipeline será interrompido.")
        logger.error("Ação necessária: Configure o 'Secret' CR_PLAYER_TAG_SEC no seu repositório GitHub.")
        sys.exit(1) # Interrompe o pipeline com erro
    elif not player_tag_sec:
        logger.warning("⚠️ Aviso: Rodando sem a Tag Secundária. O dashboard local será gerado apenas com a conta principal.")

    try:
        logger.info("FASE 1: Coletando batalhas da API e atualizando CSVs...")
        collect_main()
    except Exception as e:
        logger.error(f"Erro na FASE 1 (Coleta): {e}")
        # Prossegue para atualizar com os dados que já existem

    # 1.2 Coletar Ciclo de Baús (Fase 1 do Plano)
    try:
        logger.info("FASE 1.2: Coletando ciclo de baús...")
        from collect_chests import collect_chests
        collect_chests()
    except Exception as e:
        logger.error(f"Erro na FASE 1.2 (Baús): {e}")

    # 1.3 Coletar Meta Brasil (Fase 2 do Plano)
    try:
        logger.info("FASE 1.3: Coletando ranking Top 100 Brasil (Meta)...")
        from collect_meta_br import collect_meta_br
        collect_meta_br()
    except Exception as e:
        logger.error(f"Erro na FASE 1.3 (Meta BR): {e}")

    # 1.5 Coletar Decks de Guerra (Quinta a Domingo)
    try:
        # Quinta=3, Sexta=4, Sabado=5, Domingo=6
        hoje = datetime.now()
        if hoje.weekday() in [0, 3, 4, 5, 6]:
            logger.info("FASE 1.5: Dia de Guerra detectado! Coletando decks dos melhores jogadores...")
            from collect_war_top_decks import collect_top_decks
            from collect_war_weekend import collect_boat_data
            collect_top_decks()
            collect_boat_data()
        else:
            logger.info("FASE 1.5: Fora do periodo de guerra (Segunda a Quarta). Pulando coleta de decks.")
    except Exception as e:
        logger.error(f"Erro na FASE 1.5 (Guerra): {e}")

    # 2. Atualizar README (Histograma e Estatísticas)
    try:
        logger.info("FASE 2: Atualizando README.md com novas estatísticas...")
        updater = ReadmeCSVUpdater(csv_dir="src", readme_path="README.md")
        updater.update_readme()
    except Exception as e:
        logger.error(f"Erro na FASE 2 (README): {e}")

    # 3. Gerar Dashboard HTML Premium
    try:
        logger.info("FASE 3: Gerando Dashboard HTML Premium (index.html na raiz)...")
        generator = GitHubPagesHTMLGenerator()
        html_content = generator.generate_html_report()
        
        # Define diretório de saída
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(root_dir, 'index.html')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        # 3.2 Gerar Página do Clã (clan.html)
        logger.info("FASE 3.2: Gerando página do Clã (clan.html na raiz)...")
        clan_gen = ClanAnalyticsGenerator()
        clan_html = clan_gen.generate_clan_html_report()
        clan_path = os.path.join(root_dir, 'clan.html')
        with open(clan_path, 'w', encoding='utf-8') as f:
            f.write(clan_html)
        
        # 3.3 Gerar Páginas de Membros (member_*.html)
        logger.info("FASE 3.3: Gerando páginas individuais de membros (member_*.html na raiz)...")
        from member_generator import main as members_main
        members_main()
        
        logger.info("Dashboard e relatórios gerados com sucesso na raiz.")
    except Exception as e:
        logger.error(f"Erro na FASE 3 (HTML): {e}")

    logger.info("=" * 60)
    logger.info("SINCRONIZAÇÃO CONCLUÍDA COM SUCESSO!")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
