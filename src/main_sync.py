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
from gemini_advisor import main as gemini_main

def main():
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("INICIANDO SINCRONIZAÇÃO CLASH ROYALE (PIPELINE ÚNICO)")
    logger.info("=" * 60)
    
    # 1. Coletar Batalhas e Consolidar no CSV 2026
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

    # 1.5 Coletar Decks de Guerra (Quinta a Domingo)
    try:
        # Quinta=3, Sexta=4, Sabado=5, Domingo=6
        hoje = datetime.now()
        if hoje.weekday() in [3, 4, 5, 6]:
            logger.info("FASE 1.5: Dia de Guerra detectado! Coletando decks dos melhores jogadores...")
            from collect_war_top_decks import collect_top_decks
            from collect_war_weekend import collect_boat_data
            collect_top_decks()
            collect_boat_data()
        else:
            logger.info("FASE 1.5: Fora do periodo de guerra (Segunda a Quarta). Pulando coleta de decks.")
    except Exception as e:
        logger.error(f"Erro na FASE 1.5 (Guerra): {e}")

    # 1.6 Gerar Dicas da IA (Gemini)
    try:
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            logger.info("FASE 1.6: Gerando novas dicas com Gemini AI...")
            gemini_main()
        else:
            logger.info("FASE 1.6: GEMINI_API_KEY não configurada. Pulando dicas da IA.")
    except Exception as e:
        logger.error(f"Erro na FASE 1.6 (Gemini): {e}")

        
    # 2. Atualizar README (Histograma e Estatísticas)
    try:
        logger.info("FASE 2: Atualizando README.md com novas estatísticas...")
        updater = ReadmeCSVUpdater(csv_dir="src", readme_path="README.md")
        updater.update_readme()
    except Exception as e:
        logger.error(f"Erro na FASE 2 (README): {e}")

    # 3. Gerar Dashboard HTML Premium
    try:
        logger.info("FASE 3: Gerando Dashboard HTML Premium (docs/index.html)...")
        generator = GitHubPagesHTMLGenerator()
        html_content = generator.generate_html_report()
        
        # Define diretório de saída
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        docs_dir = os.path.join(root_dir, 'docs')
        os.makedirs(docs_dir, exist_ok=True)
        
        index_path = os.path.join(docs_dir, 'index.html')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"Dashboard gerado com sucesso em: {index_path}")
    except Exception as e:
        logger.error(f"Erro na FASE 3 (HTML): {e}")

    logger.info("=" * 60)
    logger.info("SINCRONIZAÇÃO CONCLUÍDA COM SUCESSO!")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
