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
src_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.extend([src_dir, os.path.join(src_dir, "api"), os.path.join(src_dir, "core"), os.path.join(src_dir, "generators"), os.path.join(src_dir, "utils"), os.path.join(src_dir, "legacy")])

from update_readme_from_csv import ReadmeCSVUpdater
from html_generator import GitHubPagesHTMLGenerator
from clan_generator import ClanAnalyticsGenerator
from member_generator import MemberPageGenerator

def main():
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    # Captura tempo inicial para relatorio de performance
    start_time = datetime.now()

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
    
    # Normalizacao robusta de tags no ambiente (P0 Defesa)
    tag_pri_raw = os.environ.get("CR_PLAYER_TAG", "").strip()
    if tag_pri_raw:
        tag_pri = tag_pri_raw if tag_pri_raw.startswith('#') else f"#{tag_pri_raw}"
        os.environ["CR_PLAYER_TAG"] = tag_pri
    else:
        tag_pri = None

    tag_sec_raw = os.environ.get("CR_PLAYER_TAG_SEC", "").strip()
    if tag_sec_raw and tag_sec_raw.upper() != 'NONE':
        tag_sec = tag_sec_raw if tag_sec_raw.startswith('#') else f"#{tag_sec_raw}"
        os.environ["CR_PLAYER_TAG_SEC"] = tag_sec
    else:
        tag_sec = None
        os.environ["CR_PLAYER_TAG_SEC"] = ""

    logger.info(f"Tags detectadas e normalizadas: Principal={tag_pri}, Secundaria={tag_sec}")

    # Validacao de Integridade (Seguranca para o Dashboard Multi-Conta)
    # Se estiver no GitHub Actions, a tag secundaria e OBRIGATORIA para evitar regressao do UI.
    is_github = os.environ.get("GITHUB_ACTIONS") == "true"
    
    if is_github and not tag_sec:
        logger.error("ERRO CRITICO: A variavel CR_PLAYER_TAG_SEC nao foi encontrada!")
        logger.error("Para evitar que o dashboard seja sobrescrito no formato de conta unica, o pipeline sera interrompido.")
        logger.error("Acao necessaria: Configure o 'Secret' CR_PLAYER_TAG_SEC no seu repositorio GitHub.")
        sys.exit(1) # Interrompe o pipeline com erro
    elif not tag_sec:
        logger.warning("Aviso: Rodando sem a Tag Secundaria. O dashboard local sera gerado apenas com a conta principal.")

    # Buffer para capturar logs das coletas
    collection_logs = []

    # FASE 0: Pre-flight check (Remover conflitos Git dos CSVs para nao quebrar)
    try:
        logger.info("FASE 0: Verificando e limpando conflitos Git nos arquivos CSV...")
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            from api_tools.clean_csv_conflicts import clean_csv_conflicts
            clean_csv_conflicts()
        collection_logs.append(("Git Clean", buf.getvalue()))
    except Exception as e:
        logger.error(f"Erro na FASE 0 (Git Clean): {e}")
        collection_logs.append(("Git Clean", f"ERRO: {e}"))


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
        sync_chests = os.environ.get("CR_SYNC_CHESTS", "false").lower() == "true"
        if sync_chests:
            logger.info("FASE 1.2: Coletando ciclo de baús...")
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                from collect_chests import collect_chests
                collect_chests()
            collection_logs.append(("Baus", buf.getvalue()))
        else:
            logger.info("FASE 1.2: Coleta de ciclo de baús desativada por padrao para economizar tempo.")
            collection_logs.append(("Baus", "Pulada (desativada)"))
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
                 'import sys, os; sys.path.append(os.path.join(os.getcwd(), "api")); from collect_war_top_decks import collect_top_decks; collect_top_decks()'],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300
            )
            if result.stdout: war_logs.append(result.stdout)
            if result.stderr: war_logs.append(result.stderr)
            
            result = subprocess.run(
                [sys.executable, '-c',
                 'import sys, os; sys.path.append(os.path.join(os.getcwd(), "api")); from collect_war_weekend import collect_boat_data; collect_boat_data()'],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120
            )
            if result.stdout: war_logs.append(result.stdout)
            if result.stderr: war_logs.append(result.stderr)
            
            result = subprocess.run(
                [sys.executable, '-c',
                 'import sys, os; sys.path.append(os.path.join(os.getcwd(), "api")); from collect_river_race_full import collect_river_race_intelligence; collect_river_race_intelligence()'],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900
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
        index_path = os.path.join(root_dir, 'docs', 'index.html')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        # FASE 3.2: Gerar Pagina do Cla (clan.html)
        logger.info("FASE 3.2: Gerando pagina do Cla (clan.html na raiz)...")
        clan_gen = ClanAnalyticsGenerator()
        clan_html = clan_gen.generate_clan_html_report()
        clan_path = os.path.join(root_dir, 'docs', 'clan.html')
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
                    try:
                        print(f"  [{name}] {line}")
                    except UnicodeEncodeError:
                        safe_line = line.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
                        print(f"  [{name}] {safe_line}")
            print()

    # FASE 4: Exibir Sumario Executivo Simplificado de Lutas e Dados Adicionados
    novas_lutas_pri = 0
    novas_lutas_sec = 0
    lutas_detectadas_pri = 0
    lutas_detectadas_sec = 0
    import re
    
    for name, log in collection_logs:
        if name == "Batalhas" and log:
            partes = log.split("Conta ")
            for parte in partes:
                if "Principal" in parte:
                    m_novas = re.findall(r"oponentes_ano_\d{4}\.csv:\s*\+(\d+)\s*novas", parte)
                    if m_novas:
                        novas_lutas_pri = sum(int(x) for x in m_novas)
                    m_det = re.search(r"Batalhas retornadas pela API:\s*(\d+)", parte)
                    if m_det:
                        lutas_detectadas_pri = int(m_det.group(1))
                elif "Secundaria" in parte or "Secundária" in parte:
                    m_novas = re.findall(r"oponentes_ano_\d{4}\.csv:\s*\+(\d+)\s*novas", parte)
                    if m_novas:
                        novas_lutas_sec = sum(int(x) for x in m_novas)
                    m_det = re.search(r"Batalhas retornadas pela API:\s*(\d+)", parte)
                    if m_det:
                        lutas_detectadas_sec = int(m_det.group(1))

    print("=" * 60)
    print(" ⚡ SUMARIO EXECUTIVO DE DADOS ARMAZENADOS (LUTAS)")
    print("=" * 60)
    print(f"  -> Conta Principal:")
    print(f"     - Lutas analisadas na API: {lutas_detectadas_pri}")
    print(f"     - Novas lutas adicionadas no CSV: +{novas_lutas_pri} novas lutas")
    print()
    print(f"  -> Conta Secundaria:")
    print(f"     - Lutas analisadas na API: {lutas_detectadas_sec}")
    print(f"     - Novas lutas adicionadas no CSV: +{novas_lutas_sec} novas lutas")
    print()
    
    # Verifica se houve coletas de guerra ativas
    guerra_status = "Inativa (fora de periodo ou sem novos dados)"
    for name, log in collection_logs:
        if name == "Guerra" and log:
            log_lower = log.lower()
            if "novas" in log_lower or "sucesso" in log_lower or "adicionad" in log_lower:
                guerra_status = "Ativa (dados de guerra/barcos sincronizados com sucesso)"
            elif "pulada" in log_lower:
                guerra_status = "Inativa (fora do periodo de guerra)"
            else:
                guerra_status = "Ativa (coleta concluida e consolidada)"
                
    print(f"  -> Status da Guerra: {guerra_status}")
    print("=" * 60)

    # FASE 5: Exibir Tempo de Execucao (Metricas de Performance)
    end_time = datetime.now()
    duration = end_time - start_time
    inicio_str = start_time.strftime('%Hh%M:%S')
    fim_str = end_time.strftime('%Hh%M:%S')
    tot_sec = int(duration.total_seconds())
    hours = tot_sec // 3600
    minutes = (tot_sec % 3600) // 60
    seconds = tot_sec % 60
    duracao_str = f"{hours:02d}h{minutes:02d}:{seconds:02d}"

    print(" ⏱️ TEMPO DE EXECUCAO DO PIPELINE")
    print("=" * 60)
    print(f"  -> Inicio: {inicio_str}")
    print(f"  -> Fim: {fim_str}")
    print(f"  -> Tempo Total: {duracao_str}")
    print("=" * 60)

    logger.info("=" * 60)
    logger.info("SINCRONIZACAO CONCLUIDA COM SUCESSO!")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
