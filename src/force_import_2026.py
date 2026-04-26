#!/usr/bin/env python3
"""
Script para forçar a importação das últimas batalhas da API para o arquivo oficial 2026.
Garante que o histórico seja atualizado manualmente sem depender apenas do workflow automático.
"""

import os
import sys
import io

# Configura o terminal para aceitar UTF-8 (evita erro com emojis em nomes de jogadores no Windows)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from opponents_report import OpponentsReporter

def force_import_2026():
    # Token e Tag (fallback para os valores conhecidos do projeto)
    token = os.getenv("CR_API_TOKEN", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjkwODQxMGZlLTdiNjgtNGI1Ny04YWU5LWVhMTE2YWZiODMxYyIsImlhdCI6MTc2NTQ5Mzk4OSwic3ViIjoiZGV2ZWxvcGVyLzllZjZlMmQ2LTQ1ZmEtYjdkMi1jZGI2LTZmYWJmODA0NWFiZiIsInNjb3BlcyI6WyJyb3lhbGUiXSwibGltaXRzIjpbeyJ0aWVyIjoiZGV2ZWxvcGVyL3NpbHZlciIsInR5cGUiOiJ0aHJvdHRsaW5nIn0seyJjaWRycyI6WyI0NS43OS4yMTguNzkiXSwidHlwZSI6ImNsaWVudCJ9XX0.pDhAHyZ2tAR5dg2QwBXabKTryUvaT7N9QxFKDUSrvZ_1P99x3hLP1oXy49Y9E4a4Ty_TiiUgqd5BTYzwO1Z3wA")
    tag = os.getenv("CR_PLAYER_TAG", "#2QR292P")
    
    print("=" * 60)
    print(f"IMPORTAÇÃO MANUAL DE BATALHAS - {tag}")
    print("=" * 60)
    
    # Define o arquivo de saída oficial de 2026
    output_file = os.path.join("data_csv_oficial", "oponentes_ano_2026.csv")
    
    try:
        # 1. Inicializa o reporter (isso carrega os CSVs atuais para a memória)
        print(f"Carregando histórico existente e inicializando banco de dados...")
        reporter = OpponentsReporter(token)
        
        # 2. Busca novas batalhas na API
        print(f"Buscando batalhas recentes para {tag}...")
        battles = reporter.get_battle_log(tag)
        
        if battles:
            print(f"Encontradas {len(battles)} batalhas na API.")
            # 3. Salva no banco (INSERT OR IGNORE evita duplicados)
            novas, existentes = reporter.save_battles_to_db(tag, battles)
            print(f"Merge concluído: {novas} novas, {existentes} já existiam.")
        else:
            print("Não foi possível obter batalhas da API (ou limite atingido).")
            print("Prosseguindo com a regeneração do CSV a partir do histórico local...")

        # 4. Regera o CSV oficial a partir de TODO o histórico acumulado no banco
        print(f"Regerando {output_file} com dados consolidados (2026)...")
        # Forçamos o ano 2026 e o arquivo de saída oficial
        arquivos = reporter.generate_csv_from_db(tag, year=2026, output_file=output_file)
        
        if arquivos:
            print("\n" + "=" * 60)
            print(f"SUCESSO: Arquivo {output_file} atualizado com histórico completo!")
            print(f"Total de registros agora no CSV: {sum(1 for line in open(output_file, encoding='utf-8-sig')) - 1}")
            print("=" * 60)
        else:
            print("\n[AVISO] Nenhum dado foi retornado do banco para gerar o CSV.")
        
    except Exception as e:
        print(f"\n[ERRO] Falha na importação: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Garante que estamos no diretório src para os caminhos relativos funcionarem
    if os.path.basename(os.getcwd()) != 'src' and os.path.exists('src'):
        os.chdir('src')
        
    force_import_2026()
