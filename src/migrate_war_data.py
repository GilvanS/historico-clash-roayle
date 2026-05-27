#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Migracao e Consolidadacao Historica de Dados de Guerra e Status de Barcos.
Efetua a leitura de dezenas de arquivos soltos, normaliza os layouts antigos e novos,
aplica deduplicacao inteligente e salva em arquivos acumulados mestres unicos.
"""

import os
import re
import csv
import glob
import logging
from datetime import datetime

# Configura logs sem acentos para conformidade com as regras estritas
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'data_clan')
GUERRA_HIST_FILE = os.path.join(DATA_DIR, 'guerra_historico.csv')
BARCOS_HIST_FILE = os.path.join(DATA_DIR, 'status_barcos_historico.csv')

# Mapeamento conhecido de Clans para Tags
CLAN_TAG_MAP = {
    'Tropa Do Bruxo': '#QCLPL9VQ',
    'Tropa Do Bruxo 2': '#R0JVY98R',
    'macondo': '#LLCCRCL0',
    'NORD DE FRANCE': '#QR889RG0',  # Exemplo
    'cymru warriors': '#GPQYCUCU',  # Exemplo
    'Critical THC': '#R0VJUCJP',   # Exemplo
    'Perú': '#QG9G9JCG',
    'ScdSqd': '#90P2LL8Y',
    'Peruvian': '#G8P20CCY',
    'Таллинн рулит': '#2YUCYQPC',
    'абвгд': '#SEC_CLAN_1',
    'kids with needs': '#SEC_CLAN_2',
    'BLACK「DR4GON': '#SEC_CLAN_3',
    'Babayaga': '#SEC_CLAN_4',
    'красная meсть!': '#SEC_CLAN_5',
    'красная месть!': '#SEC_CLAN_5',
}

# Traducao de dias da semana para Dia de Batalha (Quinta=Reset, Sexta=Dia 1, etc.)
WEEKDAY_TO_BATTLE_DAY = {
    3: 'Reset',  # Quinta-feira (treinamento)
    4: 'Dia 1',  # Sexta-feira (batalha)
    5: 'Dia 2',  # Sabado (batalha)
    6: 'Dia 3',  # Domingo (batalha)
    0: 'Dia 4',  # Segunda-feira (batalha final)
}

def get_battle_day_label(date_str: str) -> str:
    """Calcula o dia de batalha lógico baseando-se no dia da semana da data."""
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        wd = dt.weekday()
        return WEEKDAY_TO_BATTLE_DAY.get(wd, 'Reset')
    except:
        return 'Reset'

def parse_date_from_filename(filename: str, prefix: str) -> str:
    """Extrai data no formato YYYY-MM-DD do nome do arquivo."""
    cleaned = filename.replace(prefix, '').replace('.csv', '')
    # Tenta YYYY_MM_DD ou YYYY-MM-DD
    match = re.search(r'(\d{4})[-_](\d{2})[-_](\d{2})', cleaned)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return ""

def build_player_mappings():
    """Varre arquivos recentes para mapear Jogador -> Tag e Jogador -> Cla."""
    player_to_tag = {}
    player_to_clan = {}
    clan_to_tag = {}
    
    logger.info("Iniciando mapeamento de tags de jogadores e clans...")
    
    # 1. Mapeamento a partir de arquivos de inteligencia recentes
    intel_files = glob.glob(os.path.join(DATA_DIR, "inteligencia_guerra_*.csv"))
    for filepath in sorted(intel_files, reverse=True):
        if "_full_" in filepath:
            continue
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                cols = reader.fieldnames or []
                if 'player_nome' in cols and 'player_tag' in cols:
                    for row in reader:
                        nome = row.get('player_nome')
                        tag = row.get('player_tag')
                        clan_nome = row.get('clan_nome')
                        clan_tag = row.get('clan_tag')
                        
                        if nome and tag:
                            player_to_tag[nome.strip().upper()] = tag.strip()
                        if nome and clan_nome:
                            player_to_clan[nome.strip().upper()] = clan_nome.strip()
                        if clan_nome and clan_tag:
                            clan_to_tag[clan_nome.strip()] = clan_tag.strip()
        except Exception as e:
            logger.error(f"Erro ao ler {os.path.basename(filepath)} para mapeamento: {e}")
            
    # 2. Mapeamento estático complementar baseado no clã para robustez
    for name, tag in CLAN_TAG_MAP.items():
        if name not in clan_to_tag:
            clan_to_tag[name] = tag
            
    logger.info(f"Mapeados {len(player_to_tag)} jogadores e {len(clan_to_tag)} clans com sucesso.")
    return player_to_tag, player_to_clan, clan_to_tag

def migrate_status_barcos(clan_to_tag):
    """Consolida todos os arquivos de status_barcos em um arquivo unificado."""
    logger.info("Iniciando migracao dos dados de status de barcos...")
    
    boat_files = glob.glob(os.path.join(DATA_DIR, "status_barcos_*.csv"))
    if not boat_files:
        logger.warning("Nenhum arquivo de status de barcos encontrado para migracao.")
        return
        
    records = []
    
    for filepath in sorted(boat_files):
        filename = os.path.basename(filepath)
        # Determinar conta_tipo baseado no sufixo
        conta_tipo = 'principal'
        if '_pri_' in filename:
            conta_tipo = 'principal'
        elif '_sec_' in filename:
            conta_tipo = 'secundaria'
        else:
            # Arquivo antigo legado (todos eram da conta principal)
            conta_tipo = 'principal'
            
        data_coleta = parse_date_from_filename(filename, 'status_barcos_')
        if not data_coleta:
            # Trata formato pri/sec
            data_coleta = parse_date_from_filename(filename, 'status_barcos_pri_')
            if not data_coleta:
                data_coleta = parse_date_from_filename(filename, 'status_barcos_sec_')
                
        if not data_coleta:
            logger.warning(f"Nao foi possivel extrair data do arquivo de barcos: {filename}")
            continue
            
        dia_batalha = get_battle_day_label(data_coleta)
        
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    clan_nome = row.get('Nome_Cla', '').strip()
                    if not clan_nome:
                        continue
                        
                    clan_tag = clan_to_tag.get(clan_nome, CLAN_TAG_MAP.get(clan_nome, ''))
                    
                    records.append({
                        'data_coleta': data_coleta,
                        'dia_batalha': dia_batalha,
                        'conta_tipo': conta_tipo,
                        'posicao': row.get('Posicao', '0'),
                        'clan_nome': clan_nome,
                        'clan_tag': clan_tag,
                        'fama_atual': row.get('Fama_Atual', '0'),
                        'pontos_reparo': row.get('Pontos_Reparo', '0'),
                        'finalizado': row.get('Finalizado', 'Não'),
                        'pontos_periodo': row.get('Pontos_Periodo', '0')
                    })
        except Exception as e:
            logger.error(f"Erro ao ler arquivo de barcos {filename}: {e}")
            
    # Salvar arquivo unificado
    fieldnames = [
        'data_coleta', 'dia_batalha', 'conta_tipo', 'posicao', 
        'clan_nome', 'clan_tag', 'fama_atual', 'pontos_reparo', 
        'finalizado', 'pontos_periodo'
    ]
    
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(BARCOS_HIST_FILE, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(records)
        logger.info(f"Sucesso: {len(records)} registros salvos em {BARCOS_HIST_FILE}")
    except Exception as e:
        logger.error(f"Erro ao gravar arquivo de barcos consolidado: {e}")

def migrate_inteligencia_guerra(player_to_tag, player_to_clan, clan_to_tag):
    """Consolida todos os arquivos de inteligencia_guerra em um arquivo acumulado unico."""
    logger.info("Iniciando migracao dos dados de inteligencia de guerra...")
    
    intel_files = glob.glob(os.path.join(DATA_DIR, "inteligencia_guerra_*.csv"))
    # Exclui arquivos com '_full_' se houver, pois sao backups intermediarios
    intel_files = [f for f in intel_files if '_full_' not in os.path.basename(f)]
    
    if not intel_files:
        logger.warning("Nenhum arquivo de inteligencia de guerra encontrado para migracao.")
        return
        
    records_map = {} # Chave: (data_coleta, player_tag/nome) -> record
    
    for filepath in sorted(intel_files):
        filename = os.path.basename(filepath)
        
        data_coleta = parse_date_from_filename(filename, 'inteligencia_guerra_')
        if not data_coleta:
            logger.warning(f"Nao foi possivel extrair data do arquivo de inteligencia: {filename}")
            continue
            
        dia_batalha = get_battle_day_label(data_coleta)
        
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                cols = reader.fieldnames or []
                
                has_new_format = 'player_tag' in cols
                
                for row in reader:
                    if has_new_format:
                        # Formato novo rico em dados
                        player_nome = row.get('player_nome', '').strip()
                        player_tag = row.get('player_tag', '').strip()
                        conta_tipo = row.get('conta_tipo') or row.get('player_tag_conta', 'principal')
                        
                        if not player_nome:
                            continue
                            
                        clan_nome = row.get('clan_nome', '').strip()
                        clan_tag = row.get('clan_tag', '').strip()
                        
                        # Extrai os decks diretamente
                        deck1 = row.get('deck_1', 'N/A')
                        deck2 = row.get('deck_2', 'N/A')
                        deck3 = row.get('deck_3', 'N/A')
                        deck4 = row.get('deck_4', 'N/A')
                        
                        decks_usados = row.get('decks_usados', '0')
                        boat_attacks = row.get('boat_attacks', '0')
                        
                        rec = {
                            'data_coleta': data_coleta,
                            'dia_batalha': dia_batalha,
                            'conta_tipo': conta_tipo,
                            'player_tag': player_tag,
                            'player_nome': player_nome,
                            'player_fame': row.get('player_fame', '0'),
                            'player_posicao': row.get('player_posicao', '0'),
                            'clan_tag': clan_tag,
                            'clan_nome': clan_nome,
                            'clan_posicao': row.get('clan_posicao', '0'),
                            'clan_fame': row.get('clan_fame', '0'),
                            'decks_usados': decks_usados,
                            'boat_attacks': boat_attacks,
                            'deck_1': deck1 if deck1 else 'N/A',
                            'deck_1_tipo': row.get('deck_1_tipo', 'N/A'),
                            'deck_2': deck2 if deck2 else 'N/A',
                            'deck_2_tipo': row.get('deck_2_tipo', 'N/A'),
                            'deck_3': deck3 if deck3 else 'N/A',
                            'deck_3_tipo': row.get('deck_3_tipo', 'N/A'),
                            'deck_4': deck4 if deck4 else 'N/A',
                            'deck_4_tipo': row.get('deck_4_tipo', 'N/A'),
                            'war_vitorias': row.get('war_vitorias', '0'),
                            'war_derrotas': row.get('war_derrotas', '0'),
                            'war_medals': row.get('war_medals', '0'),
                            'war_torre': row.get('war_torre', 'Tower Princess'),
                            'war_battles_count': row.get('war_battles_count', '0')
                        }
                    else:
                        # Formato antigo simples: Ranking;Cla;Jogador;Lutou_Hoje;Ataques_Feitos;Fama_Hoje;Deck_1;Deck_2;Deck_3;Deck_4
                        player_nome = row.get('Jogador', '').strip()
                        if not player_nome:
                            continue
                            
                        # Mapear tags retroativamente para evitar perdas
                        player_key = player_nome.upper()
                        player_tag = player_to_tag.get(player_key, '')
                        if not player_tag:
                            # Caso nao mapeado, gera tag ficticia baseada no nome para nao quebrar
                            player_tag = f"#LEGACY_{player_nome.replace(' ', '').upper()}"
                            
                        clan_nome = row.get('Cla', '').strip()
                        clan_tag = clan_to_tag.get(clan_nome, CLAN_TAG_MAP.get(clan_nome, ''))
                        
                        # Extrai decks limpando a string "Deck nao encontrado no log recente"
                        def clean_deck(d):
                            if not d or "nao encontrado" in d.lower():
                                return 'N/A'
                            return d.strip()
                            
                        deck1 = clean_deck(row.get('Deck_1'))
                        deck2 = clean_deck(row.get('Deck_2'))
                        deck3 = clean_deck(row.get('Deck_3'))
                        deck4 = clean_deck(row.get('Deck_4'))
                        
                        # Calcula decks usados
                        used = 0
                        for d in [deck1, deck2, deck3, deck4]:
                            if d != 'N/A':
                                used += 1
                                
                        rec = {
                            'data_coleta': data_coleta,
                            'dia_batalha': dia_batalha,
                            'conta_tipo': 'principal',
                            'player_tag': player_tag,
                            'player_nome': player_nome,
                            'player_fame': row.get('Fama_Hoje', '0'),
                            'player_posicao': row.get('Ranking', '0'),
                            'clan_tag': clan_tag,
                            'clan_nome': clan_nome,
                            'clan_posicao': '1',
                            'clan_fame': '0',
                            'decks_usados': str(used),
                            'boat_attacks': '0',
                            'deck_1': deck1,
                            'deck_1_tipo': 'RangeBattle' if deck1 != 'N/A' else 'N/A',
                            'deck_2': deck2,
                            'deck_2_tipo': 'RangeBattle' if deck2 != 'N/A' else 'N/A',
                            'deck_3': deck3,
                            'deck_3_tipo': 'RangeBattle' if deck3 != 'N/A' else 'N/A',
                            'deck_4': deck4,
                            'deck_4_tipo': 'RangeBattle' if deck4 != 'N/A' else 'N/A',
                            'war_vitorias': '0',
                            'war_derrotas': '0',
                            'war_medals': '0',
                            'war_torre': 'Tower Princess',
                            'war_battles_count': '0'
                        }
                    
                    # === Higienizacao e Sanitizacao Geral de Dados Inflados ===
                    try:
                        vitorias = int(rec.get('war_vitorias', '0') or 0)
                    except:
                        vitorias = 0
                    try:
                        derrotas = int(rec.get('war_derrotas', '0') or 0)
                    except:
                        derrotas = 0
                    try:
                        medals = int(rec.get('war_medals', '0') or 0)
                    except:
                        medals = 0
                    try:
                        battles = int(rec.get('war_battles_count', '0') or 0)
                    except:
                        battles = 0
                    try:
                        decks = int(rec.get('decks_usados', '0') or 0)
                    except:
                        decks = 0
                    try:
                        boat = int(rec.get('boat_attacks', '0') or 0)
                    except:
                        boat = 0
                        
                    # 1. Total de batalhas não pode exceder 4 por dia
                    total_battles = vitorias + derrotas
                    if total_battles > 4:
                        vitorias = min(4, vitorias)
                        derrotas = min(4 - vitorias, derrotas)
                        battles = vitorias + derrotas
                    
                    if battles > 4:
                        battles = 4
                        
                    # 2. Recalculo estrito e limite maximo de medals (fama diaria real - teto supremo de 900)
                    if medals > 900 or (vitorias > 0 or derrotas > 0):
                        # Se contiver vitorias e derrotas estimadas
                        medals = (vitorias * 200) + (derrotas * 100)
                        # Fallback se as rodadas de duelo indicarem mais vitorias/derrotas que ultrapassem a fama convencional
                        if medals == 0 and decks > 0:
                            medals = min(900, decks * 100) # fallback seguro (derrotas)
                        elif medals > 900:
                            medals = 900
                    else:
                        # Se as medalhas vierem sem vitórias/derrotas gravadas mas vierem exageradas (> 900)
                        if medals > 900:
                            medals = 900
                            
                    # Garantir que decks_usados seja coerente (no maximo 4)
                    if decks > 4:
                        decks = 4
                        
                    # Atualizar o registro rec com os dados higienizados
                    rec['war_vitorias'] = str(vitorias)
                    rec['war_derrotas'] = str(derrotas)
                    rec['war_medals'] = str(medals)
                    rec['war_battles_count'] = str(battles)
                    rec['decks_usados'] = str(decks)
                    rec['boat_attacks'] = str(boat)
                    
                    # Filtrar inativos absolutos: salvar apenas quem realmente participou da guerra
                    # Em dias de batalha (Dia 1, Dia 2, Dia 3, Dia 4), a participacao exige uso de deck ou ataque de barco.
                    # No dia de Reset (Quinta-feira / Reset), permitimos participacao se houver fama/medalhas (fallback do Reset).
                    dia_batalha_lbl = rec.get('dia_batalha', 'Reset')
                    if dia_batalha_lbl == 'Reset':
                        participou = (decks > 0 or boat > 0 or medals > 0 or battles > 0)
                    else:
                        participou = (decks > 0 or boat > 0)
                        
                    if not participou:
                        continue
                    
                    # Deduplicacao inteligente por chave unica: (data, tag)
                    key = (data_coleta, rec['player_tag'])
                    
                    if key in records_map:
                        existing = records_map[key]
                        # Mantem o registro que tiver mais decks preenchidos ou maior fama
                        ex_decks = int(existing['decks_usados'])
                        new_decks = int(rec['decks_usados'])
                        ex_fame = int(existing['player_fame'])
                        new_fame = int(rec['player_fame'])
                        
                        if new_decks > ex_decks or (new_decks == ex_decks and new_fame > ex_fame):
                            records_map[key] = rec
                    else:
                        records_map[key] = rec
                        
        except Exception as e:
            logger.error(f"Erro ao ler arquivo de inteligencia {filename}: {e}")
            
    # Salvar arquivo unificado
    fieldnames = [
        'data_coleta', 'dia_batalha', 'conta_tipo', 'player_tag', 'player_nome', 
        'player_fame', 'player_posicao', 'clan_tag', 'clan_nome', 'clan_posicao', 
        'clan_fame', 'decks_usados', 'boat_attacks', 
        'deck_1', 'deck_1_tipo', 'deck_2', 'deck_2_tipo', 
        'deck_3', 'deck_3_tipo', 'deck_4', 'deck_4_tipo',
        'war_vitorias', 'war_derrotas', 'war_medals', 'war_torre', 'war_battles_count'
    ]
    
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(GUERRA_HIST_FILE, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            
            # Ordena os registros por data decrescente e fama decrescente do jogador
            sorted_records = sorted(
                records_map.values(),
                key=lambda x: (x['data_coleta'], -int(x['player_fame'])),
                reverse=True
            )
            writer.writerows(sorted_records)
            
        logger.info(f"Sucesso: {len(records_map)} registros salvos em {GUERRA_HIST_FILE}")
    except Exception as e:
        logger.error(f"Erro ao gravar arquivo de inteligencia de guerra consolidado: {e}")

def run_migration():
    """Roda todo o fluxo de migracao de dados."""
    logger.info("=" * 60)
    logger.info("INICIANDO FLUXO DE MIGRACAO DE DADOS HISTORICOS")
    logger.info("=" * 60)
    
    player_to_tag, player_to_clan, clan_to_tag = build_player_mappings()
    
    migrate_status_barcos(clan_to_tag)
    migrate_inteligencia_guerra(player_to_tag, player_to_clan, clan_to_tag)
    
    logger.info("=" * 60)
    logger.info("FLUXO DE MIGRACAO DE DADOS CONCLUIDO COM SUCESSO")
    logger.info("=" * 60)

if __name__ == "__main__":
    run_migration()
