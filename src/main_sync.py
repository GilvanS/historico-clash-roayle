#!/usr/bin/env python3
"""
Mestre da Sincronização Clash Royale (30 MIN)
Orquestra: Coleta -> Consolidação -> README -> Dashboard HTML
Logs de coleta sao capturados e exibidos APENAS no final para clareza.
"""

import os
import sys
import logging
import io
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime

# Adiciona o diretório src ao path se necessário
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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
    # Se estiver no GitHub Actions, a tag secundaria e OBRIGATORIA para evitar regressao do UI.
    is_github = os.environ.get("GITHUB_ACTIONS") == "true"
    player_tag_sec = os.environ.get("CR_PLAYER_TAG_SEC")
    
    if is_github and not player_tag_sec:
        logger.error("ERRO CRITICO: A variavel CR_PLAYER_TAG_SEC nao foi encontrada!")
        logger.error("Para evitar que o dashboard seja sobrescrito no formato de conta unica, o pipeline sera interrompido.")
        logger.error("Acao necessaria: Configure o 'Secret' CR_PLAYER_TAG_SEC no seu repositorio GitHub.")
        sys.exit(1) # Interrompe o pipeline com erro
    elif not player_tag_sec:
        logger.warning("Aviso: Rodando sem a Tag Secundaria. O dashboard local sera gerado apenas com a conta principal.")

    # Buffer para capturar logs das coletas
    collection_logs = []

    # FASE 1: Coletar batalhas
    try:
        logger.info("FASE 1: Coletando batalhas da API e atualizando CSVs...")
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            from collect_battles_csv import main as collect_main
            collect_main()
        collection_logs.append(("Batalhas", buf.getvalue()))
    except Exception as e:
        logger.error(f"Erro na FASE 1 (Coleta): {e}")
        collection_logs.append(("Batalhas", f"ERRO: {e}"))

    # FASE 1.2: Coletar Ciclo de Baús
    try:
        logger.info("FASE 1.2: Coletando ciclo de baús...")
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            from collect_chests import collect_chests
            collect_chests()
        collection_logs.append(("Baus", buf.getvalue()))
    except Exception as e:
        logger.error(f"Erro na FASE 1.2 (Baus): {e}")
        collection_logs.append(("Baus", f"ERRO: {e}"))

    # FASE 1.3: Coletar Meta Brasil
    try:
        logger.info("FASE 1.3: Coletando ranking Top 100 Brasil (Meta)...")
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            from collect_meta_br import collect_meta_br
            collect_meta_br()
        collection_logs.append(("Meta BR", buf.getvalue()))
    except Exception as e:
        logger.error(f"Erro na FASE 1.3 (Meta BR): {e}")
        collection_logs.append(("Meta BR", f"ERRO: {e}"))

    # FASE 1.5: Coletar Decks de Guerra (Quinta 7h00 a Segunda 6h59)
    try:
        hoje = datetime.now()
        hora = hoje.hour
        dia_semana = hoje.weekday()  # 0=Seg, 1=Ter, 2=Qua, 3=Qui, 4=Sex, 5=Sab, 6=Dom
        
        # Regra: Guerra vai de Quinta 7h00 ate Segunda 6h59
        # Quinta (3): so coleta se hora >= 7
        # Sexta (4), Sabado (5), Domingo (6): coleta sempre
        # Segunda (0): so coleta se hora < 7
        # Terca (1), Quarta (2): nunca coleta
        is_war_period = False
        if dia_semana == 3 and hora >= 7:  # Quinta apos 7h
            is_war_period = True
        elif dia_semana in [4, 5, 6]:  # Sexta, Sabado, Domingo
            is_war_period = True
        elif dia_semana == 0 and hora < 7:  # Segunda antes de 7h
            is_war_period = True
        
        if is_war_period:
            logger.info("FASE 1.5: Periodo de Guerra ativo! Coletando decks dos melhores jogadores...")
            war_logs = []
            # Nota: Alguns scripts de guerra usam sys.stdout.buffer, incompativel com redirect_stdout
            # Executamos normalmente e capturamos apenas o que for possivel
            import subprocess
            result = subprocess.run(
                [sys.executable, '-c',
                 'from collect_war_top_decks import collect_top_decks; collect_top_decks()'],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True, text=True, timeout=120
            )
            if result.stdout: war_logs.append(result.stdout)
            if result.stderr: war_logs.append(result.stderr)
            
            result = subprocess.run(
                [sys.executable, '-c',
                 'from collect_war_weekend import collect_boat_data; collect_boat_data()'],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True, text=True, timeout=120
            )
            if result.stdout: war_logs.append(result.stdout)
            if result.stderr: war_logs.append(result.stderr)
            
            result = subprocess.run(
                [sys.executable, '-c',
                 'from collect_river_race_full import collect_river_race_intelligence; collect_river_race_intelligence()'],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True, text=True, timeout=120
            )
            if result.stdout: war_logs.append(result.stdout)
            if result.stderr: war_logs.append(result.stderr)
            
            collection_logs.append(("Guerra", "\n".join(war_logs)))
        else:
            logger.info("FASE 1.5: Fora do periodo de guerra. Pulando coleta de decks.")
            collection_logs.append(("Guerra", "Pulada (fora do periodo de guerra)"))
    except Exception as e:
        logger.error(f"Erro na FASE 1.5 (Guerra): {e}")
        collection_logs.append(("Guerra", f"ERRO: {e}"))

    # FASE 2: Atualizar README
    try:
        logger.info("FASE 2: Atualizando README.md com novas estatisticas...")
        updater = ReadmeCSVUpdater(csv_dir="src", readme_path="README.md")
        updater.update_readme()
    except Exception as e:
        logger.error(f"Erro na FASE 2 (README): {e}")

    # FASE 3: Gerar Dashboard HTML Premium
    try:
        logger.info("FASE 3: Gerando Dashboard HTML Premium (index.html na raiz)...")
        generator = GitHubPagesHTMLGenerator()
        html_content = generator.generate_html_report()
        
        # Define diretorio de saida
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(root_dir, 'index.html')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        # FASE 3.2: Gerar Pagina do Cla (clan.html)
        logger.info("FASE 3.2: Gerando pagina do Cla (clan.html na raiz)...")
        clan_gen = ClanAnalyticsGenerator()
        clan_html = clan_gen.generate_clan_html_report()
        clan_path = os.path.join(root_dir, 'clan.html')
        with open(clan_path, 'w', encoding='utf-8') as f:
            f.write(clan_html)
        
        # FASE 3.3: Gerar Paginas de Membros (member_*.html)
        logger.info("FASE 3.3: Gerando paginas individuais de membros (member_*.html na raiz)...")
        from member_generator import main as members_main
        members_main()
        
        logger.info("Dashboard e relatorios gerados com sucesso na raiz.")
    except Exception as e:
        logger.error(f"Erro na FASE 3 (HTML): {e}")

    # RESUMO FINAL: Exibe logs das coletas agora que tudo foi processado
    logger.info("=" * 60)
    logger.info("RESUMO DAS COLETAS")
    logger.info("=" * 60)
    for name, log in collection_logs:
        if log and log.strip():
            # Imprime o log da coleta sem prefixo de timestamp para clareza
            for line in log.strip().split('\n'):
                if line.strip():
                    print(f"  [{name}] {line}")
            print()

    logger.info("=" * 60)
    logger.info("SINCRONIZACAO CONCLUÍDA COM SUCESSO!")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
