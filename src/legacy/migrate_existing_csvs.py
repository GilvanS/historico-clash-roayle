#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migracao para o esquema enriquecido de dados do Clash Royale.
Insere e calcula retroativamente as 7 novas colunas nos CSVs historicos:
- elixir_medio_jogador
- elixir_medio_oponente
- evolucoes_jogador
- evolucoes_oponente
- nivel_medio_deck_jogador
- nivel_medio_deck_oponente
- tag_clan_oponente

Garante compatibilidade total e preservacao absoluta dos dados.
"""

import os
import csv
import sys
import shutil

# Configurar stdout para UTF-8 de forma segura
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Diretorios e Caminhos
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SRC_DIR, '..', 'data', 'csv')
CARDS_MASTER_PATH = os.path.join(DATA_DIR, "cards_master_icons.csv")

# Esquema de colunas atualizado
FIELDNAMES = [
    'player_tag',
    'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente',
    'trofes_oponente', 'clan_oponente', 'resultado',
    'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
    'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente', 'vezes_enfrentado',
    'elixir_vazado_jogador', 'elixir_vazado_oponente', 'nivel_torre_jogador',
    'vida_torre_rei_jogador', 'vida_torre_rei_oponente', 
    'vida_torres_princesa_jogador', 'vida_torres_princesa_oponente',
    'trofes_iniciais_jogador', 'trofes_finais_jogador',
    'posicao_global_jogador', 'posicao_global_oponente', 'nivel_torre_oponente',
    'torre_jogador', 'torre_oponente',
    'elixir_medio_jogador', 'elixir_medio_oponente',
    'evolucoes_jogador', 'evolucoes_oponente',
    'nivel_medio_deck_jogador', 'nivel_medio_deck_oponente',
    'tag_clan_oponente'
]

def load_cards_master():
    """Carrega o dicionario de elixir e raridade a partir de cards_master_icons.csv"""
    cards_map = {}
    if not os.path.exists(CARDS_MASTER_PATH):
        print(f"[AVISO] cards_master_icons.csv nao encontrado em: {CARDS_MASTER_PATH}")
        return cards_map

    try:
        with open(CARDS_MASTER_PATH, 'r', encoding='utf-8-sig') as f:
            first_line = f.readline()
            f.seek(0)
            delim = ';' if ';' in first_line else ','
            reader = csv.DictReader(f, delimiter=delim)
            for row in reader:
                name = row.get('card_name')
                if name:
                    try:
                        elixir = int(row.get('elixir', 0))
                    except:
                        elixir = 0
                    cards_map[name.strip().lower()] = {
                        'elixir': elixir,
                        'rarity': row.get('rarity', 'common').strip().lower()
                    }
        print(f"Cards Master carregado com {len(cards_map)} cartas.")
    except Exception as e:
        print(f"[ERRO] Falha ao carregar Cards Master: {e}")
    return cards_map

def calculate_deck_average_elixir(deck_str, cards_map):
    """Calcula a media de elixir de um deck de cartas separado por ' | '"""
    if not deck_str or not isinstance(deck_str, str):
        return 0.0
    cards = [c.strip().lower() for c in deck_str.split('|') if c.strip()]
    if not cards:
        return 0.0
    
    total_elixir = 0
    found_count = 0
    for card in cards:
        if card in cards_map:
            total_elixir += cards_map[card]['elixir']
            found_count += 1
            
    if found_count == 0:
        return 0.0
    return round(total_elixir / found_count, 2)

def migrate_csv_file(file_path, cards_map):
    """Realiza a migracao e enriquecimento de um unico arquivo CSV de forma segura."""
    if not os.path.exists(file_path):
        print(f"Arquivo nao encontrado: {file_path}")
        return

    print(f"\nIniciando migracao para: {os.path.basename(file_path)}")
    
    # 1. Criar backup de seguranca antes de fazer qualquer alteracao
    backup_path = file_path + ".bak_migration_schema"
    try:
        shutil.copy2(file_path, backup_path)
        print(f"  - Backup de seguranca criado em: {os.path.basename(backup_path)}")
    except Exception as e:
        print(f"  - [ERRO CRITICO] Falha ao criar backup. Abortando migracao: {e}")
        return

    # 2. Ler os dados do CSV existente
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            first_line = f.readline()
            f.seek(0)
            delim = ';' if ';' in first_line else ','
            reader = csv.DictReader(f, delimiter=delim)
            rows = list(reader)
    except Exception as e:
        print(f"  - [ERRO] Falha ao ler o arquivo {os.path.basename(file_path)}: {e}")
        return

    if not rows:
        print("  - Arquivo vazio, nenhuma linha para processar.")
        return

    print(f"  - Total de registros lidos: {len(rows)}")

    # 3. Processar cada linha e enriquecer com as novas colunas
    migrated_rows = []
    enriched_count = 0
    for row in rows:
        # Enriquecer elixir se o campo nao estiver preenchido ou for '0.0'
        elixir_j = row.get('elixir_medio_jogador')
        if not elixir_j or float(elixir_j) == 0.0:
            row['elixir_medio_jogador'] = calculate_deck_average_elixir(row.get('deck_jogador', ''), cards_map)
            enriched_count += 1
        else:
            row['elixir_medio_jogador'] = round(float(elixir_j), 2)

        elixir_o = row.get('elixir_medio_oponente')
        if not elixir_o or float(elixir_o) == 0.0:
            row['elixir_medio_oponente'] = calculate_deck_average_elixir(row.get('deck_oponente', ''), cards_map)
        else:
            row['elixir_medio_oponente'] = round(float(elixir_o), 2)

        # Garantir preenchimento dos campos de evolucoes e niveis com padrao inteligente
        if 'evolucoes_jogador' not in row or row['evolucoes_jogador'] is None:
            row['evolucoes_jogador'] = ""
        if 'evolucoes_oponente' not in row or row['evolucoes_oponente'] is None:
            row['evolucoes_oponente'] = ""
            
        if 'nivel_medio_deck_jogador' not in row or not row['nivel_medio_deck_jogador']:
            row['nivel_medio_deck_jogador'] = 0.0
        else:
            row['nivel_medio_deck_jogador'] = round(float(row['nivel_medio_deck_jogador']), 2)
            
        if 'nivel_medio_deck_oponente' not in row or not row['nivel_medio_deck_oponente']:
            row['nivel_medio_deck_oponente'] = 0.0
        else:
            row['nivel_medio_deck_oponente'] = round(float(row['nivel_medio_deck_oponente']), 2)

        if 'tag_clan_oponente' not in row or row['tag_clan_oponente'] is None:
            row['tag_clan_oponente'] = ""

        # Mantem tag limpa e garante consistencia
        if 'player_tag' not in row or not row['player_tag']:
            row['player_tag'] = ""

        # Limpar chaves antigas que nao estao no esquema oficial
        cleaned_row = {k: row[k] for k in FIELDNAMES if k in row}
        # Preencher colunas faltantes com padrao
        for k in FIELDNAMES:
            if k not in cleaned_row:
                cleaned_row[k] = ""
                
        migrated_rows.append(cleaned_row)

    # 4. Gravar o novo arquivo CSV atualizado de volta no disco
    try:
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=';', extrasaction='ignore')
            writer.writeheader()
            writer.writerows(migrated_rows)
        print(f"  - [SUCESSO] Arquivo {os.path.basename(file_path)} re-gravado e migrado.")
        print(f"  - Registros processados: {len(migrated_rows)}, Enriquecidos retroativamente: {enriched_count}")
    except Exception as e:
        print(f"  - [ERRO GRAVE] Falha ao gravar arquivo migrado: {e}")
        print(f"  - Restaurando backup original de seguranca...")
        try:
            shutil.copy2(backup_path, file_path)
            print("  - Backup restaurado com sucesso!")
        except Exception as re:
            print(f"  - [ERRO CRITICO] Falha ao restaurar backup: {re}")

def main():
    print("=" * 60)
    print("MIGRACAO E ENRIQUECIMENTO DE DADOS HISTORICOS CLASH ROYALE")
    print("=" * 60)
    
    cards_map = load_cards_master()
    
    # Lista de arquivos oficiais para migrar
    target_files = [
        os.path.join(DATA_DIR, "oponentes_ano_2026.csv"),
        os.path.join(DATA_DIR, "historico_completo_2023_2025.csv"),
        os.path.join(DATA_DIR, "dados_manuais_preservados.csv"),
        os.path.join(DATA_DIR, "extracao_especifica_maio_2026_FINAL.csv")
    ]
    
    for fp in target_files:
        if os.path.exists(fp):
            migrate_csv_file(fp, cards_map)
        else:
            print(f"Arquivo pulado (nao existe): {os.path.basename(fp)}")
            
    print("\n" + "=" * 60)
    print("MIGRACAO DE ESQUEMA CONCLUIDA COM TOTAL SUCESSO!")
    print("=" * 60)

if __name__ == "__main__":
    main()
