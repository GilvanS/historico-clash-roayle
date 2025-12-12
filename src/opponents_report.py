#!/usr/bin/env python3
"""
Script para gerar relatorio CSV dos oponentes enfrentados no ano
Identifica se enfrentou alguem repetidamente durante o periodo
"""

import os
import sys
import csv
import sqlite3
import argparse
import requests
import json
from datetime import datetime, timedelta
from collections import Counter
from typing import List, Dict, Optional

class OpponentsReporter:
    def __init__(self, api_token: str, db_path: str = "oponentes.db"):
        self.api_token = api_token
        self.base_url = "https://proxy.royaleapi.dev/v1"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        self.db_path = db_path
        self.init_database()
        self.init_database()
    
    def init_database(self):
        """Inicializa o banco de dados SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS oponentes_batalhas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_tag TEXT,
                battle_time TEXT,
                data_formatada TEXT,
                nome_oponente TEXT,
                tag_oponente TEXT,
                nivel_oponente INTEGER,
                trofes_oponente INTEGER,
                clan_oponente TEXT,
                resultado TEXT,
                coroas_jogador INTEGER,
                coroas_oponente INTEGER,
                mudanca_trofes INTEGER,
                modo_jogo TEXT,
                tipo_batalha TEXT,
                arena TEXT,
                deck_jogador TEXT,
                deck_oponente TEXT,
                UNIQUE(player_tag, battle_time, tag_oponente)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_battles_to_db(self, player_tag: str, battles: List[Dict]):
        """Salva batalhas no banco de dados (evita duplicatas)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        novas_batalhas = 0
        batalhas_existentes = 0
        
        for battle in battles:
            opponent_info = self.extract_opponent_info(battle, player_tag)
            if not opponent_info:
                continue
            
            # Formata deck do jogador
            teams = battle.get('team', [])
            player_team = None
            for team in teams:
                if team.get('tag') == player_tag:
                    player_team = team
                    break
            
            deck_jogador = self.format_deck(player_team.get('cards', [])) if player_team else ''
            
            # Formata deck do oponente
            opponents = battle.get('opponent', [])
            opponent_team = opponents[0] if opponents else None
            deck_oponente = self.format_deck(opponent_team.get('cards', [])) if opponent_team else ''
            
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO oponentes_batalhas 
                    (player_tag, battle_time, data_formatada, nome_oponente, tag_oponente,
                     nivel_oponente, trofes_oponente, clan_oponente, resultado,
                     coroas_jogador, coroas_oponente, mudanca_trofes, modo_jogo,
                     tipo_batalha, arena, deck_jogador, deck_oponente)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_tag,
                    battle.get('battleTime', ''),
                    opponent_info['data'],
                    opponent_info['nome_oponente'],
                    opponent_info['tag_oponente'],
                    opponent_info['nivel_oponente'],
                    opponent_info['trofes_oponente'],
                    opponent_info['clan_oponente'],
                    opponent_info['resultado'],
                    opponent_info['coroas_jogador'],
                    opponent_info['coroas_oponente'],
                    opponent_info['mudanca_trofes'],
                    opponent_info['modo_jogo'],
                    opponent_info['tipo_batalha'],
                    opponent_info['arena'],
                    deck_jogador,
                    deck_oponente
                ))
                
                if cursor.rowcount > 0:
                    novas_batalhas += 1
                else:
                    batalhas_existentes += 1
            except sqlite3.Error as e:
                print(f"Erro ao salvar batalha: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        return novas_batalhas, batalhas_existentes
    
    def format_deck(self, cards: List[Dict]) -> str:
        """Formata deck de cartas como string"""
        if not cards:
            return ''
        card_names = [card.get('name', '') for card in cards]
        return ' | '.join(sorted(card_names))
    
    def get_battle_log(self, player_tag: str) -> Optional[List[Dict]]:
        """Busca o historico de batalhas da API"""
        clean_tag = player_tag.replace('#', '')
        url = f"{self.base_url}/players/%23{clean_tag}/battlelog"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Erro ao buscar historico de batalhas: {e}")
            return None
    
    def filter_battles_by_year(self, battles: List[Dict], year: int = None, all_battles: bool = False) -> List[Dict]:
        """Filtra batalhas do ano especificado (padrao: ano atual) ou retorna todas se all_battles=True"""
        if all_battles:
            return battles
        
        if year is None:
            year = datetime.now().year
        
        filtered = []
        for battle in battles:
            try:
                # battleTime vem no formato ISO: "20240115T123456.000Z"
                battle_time_str = battle.get('battleTime', '')
                if battle_time_str:
                    # Extrai o ano da string
                    battle_year = int(battle_time_str[:4])
                    if battle_year == year:
                        filtered.append(battle)
            except (ValueError, IndexError):
                continue
        
        return filtered
    
    def extract_opponent_info(self, battle: Dict, player_tag: str) -> Optional[Dict]:
        """Extrai informacoes do oponente de uma batalha"""
        # Busca o time do jogador
        teams = battle.get('team', [])
        player_team = None
        
        for team in teams:
            if team.get('tag') == player_tag:
                player_team = team
                break
        
        if not player_team:
            return None
        
        # Busca dados do oponente
        opponents = battle.get('opponent', [])
        opponent_team = opponents[0] if opponents else None
        
        if not opponent_team:
            return None
        
        # Determina resultado
        player_crowns = player_team.get('crowns', 0)
        opponent_crowns = opponent_team.get('crowns', 0)
        
        if player_crowns > opponent_crowns:
            result = 'Vitoria'
        elif player_crowns < opponent_crowns:
            result = 'Derrota'
        else:
            result = 'Empate'
        
        # Formata data
        battle_time_str = battle.get('battleTime', '')
        formatted_date = self.format_battle_date(battle_time_str)
        
        return {
            'data': formatted_date,
            'nome_oponente': opponent_team.get('name', 'Desconhecido'),
            'tag_oponente': opponent_team.get('tag', ''),
            'nivel_oponente': opponent_team.get('expLevel', 0),
            'trofes_oponente': opponent_team.get('startingTrophies', 0),
            'clan_oponente': opponent_team.get('clan', {}).get('name', 'Sem cla'),
            'resultado': result,
            'coroas_jogador': player_crowns,
            'coroas_oponente': opponent_crowns,
            'mudanca_trofes': player_team.get('trophyChange', 0),
            'modo_jogo': battle.get('gameMode', {}).get('name', 'Desconhecido'),
            'tipo_batalha': battle.get('type', 'Desconhecido'),
            'arena': battle.get('arena', {}).get('name', 'Desconhecido')
        }
    
    def format_battle_date(self, battle_time_str: str) -> str:
        """Formata a data da batalha para formato legivel"""
        try:
            # Formato: "20240115T123456.000Z"
            if len(battle_time_str) >= 8:
                year = battle_time_str[:4]
                month = battle_time_str[4:6]
                day = battle_time_str[6:8]
                hour = battle_time_str[9:11] if len(battle_time_str) > 9 else '00'
                minute = battle_time_str[11:13] if len(battle_time_str) > 11 else '00'
                return f"{day}/{month}/{year} {hour}:{minute}"
        except (ValueError, IndexError):
            pass
        return battle_time_str
    
    def generate_csv_from_db(self, player_tag: str, year: int = None, output_file: str = None, all_battles: bool = False):
        """Gera CSV a partir do banco de dados (dados acumulados)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if all_battles:
            query = "SELECT * FROM oponentes_batalhas WHERE player_tag = ? ORDER BY battle_time DESC"
            params = (player_tag,)
        else:
            if year is None:
                year = datetime.now().year
            query = "SELECT * FROM oponentes_batalhas WHERE player_tag = ? AND strftime('%Y', battle_time) = ? ORDER BY battle_time DESC"
            params = (player_tag, str(year))
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            print("Nenhuma batalha encontrada no banco de dados.")
            return
        
        # Converte para dicionarios
        opponents_data = []
        for row in rows:
            opponents_data.append({
                'data': row[3],  # data_formatada
                'nome_oponente': row[4],
                'tag_oponente': row[5],
                'nivel_oponente': row[6],
                'trofes_oponente': row[7],
                'clan_oponente': row[8],
                'resultado': row[9],
                'coroas_jogador': row[10],
                'coroas_oponente': row[11],
                'mudanca_trofes': row[12],
                'modo_jogo': row[13],
                'tipo_batalha': row[14],
                'arena': row[15],
                'deck_jogador': row[16],
                'deck_oponente': row[17]
            })
        
        # Conta repeticoes
        opponent_tags = [op['tag_oponente'] for op in opponents_data if op['tag_oponente']]
        opponent_counts = Counter(opponent_tags)
        
        # Adiciona contador de repeticoes
        for opponent_info in opponents_data:
            tag = opponent_info['tag_oponente']
            count = opponent_counts.get(tag, 0)
            opponent_info['vezes_enfrentado'] = count
        
        # Gera CSV
        fieldnames = [
            'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente', 
            'trofes_oponente', 'clan_oponente', 'resultado', 
            'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
            'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente', 'vezes_enfrentado'
        ]
        
        if output_file is None:
            if all_battles:
                output_file = "oponentes_todos.csv"
            else:
                output_file = f"oponentes_{year}.csv"
        
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(opponents_data)
        
        print(f"\nRelatorio gerado do banco de dados: {output_file}")
        print(f"Total de oponentes unicos: {len(opponent_counts)}")
        print(f"Total de batalhas registradas: {len(opponents_data)}")
        
        # Mostra oponentes repetidos
        repeated = {tag: count for tag, count in opponent_counts.items() if count > 1}
        if repeated:
            print(f"\nOponentes enfrentados mais de uma vez ({len(repeated)}):")
            sorted_repeated = sorted(repeated.items(), key=lambda x: x[1], reverse=True)
            for tag, count in sorted_repeated[:10]:
                opponent_name = next((op['nome_oponente'] for op in opponents_data if op['tag_oponente'] == tag), tag)
                print(f"  - {opponent_name} ({tag}): {count} vezes")
        else:
            print("\nNenhum oponente foi enfrentado mais de uma vez no periodo.")
    
    def generate_period_csvs(self, player_tag: str):
        """Gera CSVs para dia, semana, mes e ano atual (acumulados do banco)"""
        now = datetime.now()
        
        # Periodo: Dia atual
        dia_inicio = now.replace(hour=0, minute=0, second=0, microsecond=0)
        dia_fim = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Periodo: Semana atual (segunda a domingo)
        dias_semana = now.weekday()  # 0 = segunda, 6 = domingo
        semana_inicio = (now - timedelta(days=dias_semana)).replace(hour=0, minute=0, second=0, microsecond=0)
        semana_fim = now
        
        # Periodo: Mes atual
        mes_inicio = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        mes_fim = now
        
        # Periodo: Ano atual
        ano_inicio = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        ano_fim = now
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Funcao auxiliar para formatar data para query SQL (formato: 20240115T123456)
        def format_date_for_query(dt):
            return dt.strftime('%Y%m%dT%H%M%S')
        
        # Busca batalhas por periodo
        periodos = {
            'dia': {
                'inicio': format_date_for_query(dia_inicio),
                'fim': format_date_for_query(dia_fim),
                'arquivo': f"oponentes_dia_{now.strftime('%Y%m%d')}.csv"
            },
            'semana': {
                'inicio': format_date_for_query(semana_inicio),
                'fim': format_date_for_query(semana_fim),
                'arquivo': f"oponentes_semana_{now.strftime('%Y%W')}.csv"
            },
            'mes': {
                'inicio': format_date_for_query(mes_inicio),
                'fim': format_date_for_query(mes_fim),
                'arquivo': f"oponentes_mes_{now.strftime('%Y%m')}.csv"
            },
            'ano': {
                'inicio': format_date_for_query(ano_inicio),
                'fim': format_date_for_query(ano_fim),
                'arquivo': f"oponentes_ano_{now.year}.csv"
            }
        }
        
        arquivos_gerados = []
        
        for periodo_nome, periodo_info in periodos.items():
            # Query usando comparacao de strings (battle_time formato: 20240115T123456.000Z)
            query = """
                SELECT * FROM oponentes_batalhas 
                WHERE player_tag = ? 
                AND substr(battle_time, 1, 15) >= ? 
                AND substr(battle_time, 1, 15) <= ?
                ORDER BY battle_time DESC
            """
            params = (player_tag, periodo_info['inicio'], periodo_info['fim'])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            if not rows:
                print(f"Nenhuma batalha encontrada para o periodo {periodo_nome}.")
                continue
            
            # Converte para dicionarios
            opponents_data = []
            for row in rows:
                opponents_data.append({
                    'data': row[3],
                    'nome_oponente': row[4],
                    'tag_oponente': row[5],
                    'nivel_oponente': row[6],
                    'trofes_oponente': row[7],
                    'clan_oponente': row[8],
                    'resultado': row[9],
                    'coroas_jogador': row[10],
                    'coroas_oponente': row[11],
                    'mudanca_trofes': row[12],
                    'modo_jogo': row[13],
                    'tipo_batalha': row[14],
                    'arena': row[15],
                    'deck_jogador': row[16],
                    'deck_oponente': row[17]
                })
            
            # Conta repeticoes
            opponent_tags = [op['tag_oponente'] for op in opponents_data if op['tag_oponente']]
            opponent_counts = Counter(opponent_tags)
            
            # Adiciona contador de repeticoes
            for opponent_info in opponents_data:
                tag = opponent_info['tag_oponente']
                count = opponent_counts.get(tag, 0)
                opponent_info['vezes_enfrentado'] = count
            
            # Gera CSV (append mode para acumular)
            fieldnames = [
                'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente', 
                'trofes_oponente', 'clan_oponente', 'resultado', 
                'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
                'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente', 'vezes_enfrentado'
            ]
            
            output_file = periodo_info['arquivo']
            
            # Verifica se arquivo existe para determinar se deve append ou write
            file_exists = os.path.exists(output_file)
            
            # Sempre reescreve o arquivo com dados atualizados do banco (acumulado)
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(opponents_data)
            
            arquivos_gerados.append(output_file)
            print(f"CSV {periodo_nome} gerado: {output_file} ({len(opponents_data)} batalhas)")
        
        conn.close()
        
        return arquivos_gerados
    
    def generate_csv_report(self, player_tag: str, year: int = None, output_file: str = None, all_battles: bool = False, save_to_db: bool = True):
        """Gera relatorio CSV dos oponentes enfrentados"""
        if all_battles:
            year_label = "todas as batalhas disponiveis"
            if output_file is None:
                output_file = "oponentes_todos.csv"
        else:
            if year is None:
                year = datetime.now().year
            year_label = f"ano {year}"
            if output_file is None:
                output_file = f"oponentes_{year}.csv"
        
        print(f"Buscando {year_label}...")
        
        # Busca historico de batalhas
        battles = self.get_battle_log(player_tag)
        if not battles:
            print("Nenhuma batalha encontrada ou erro ao buscar dados.")
            return
        
        print(f"Total de batalhas encontradas na API: {len(battles)}")
        
        # Salva no banco de dados se solicitado
        if save_to_db:
            novas, existentes = self.save_battles_to_db(player_tag, battles)
            print(f"Batalhas novas salvas: {novas}")
            print(f"Batalhas ja existentes (ignoradas): {existentes}")
        
        # Filtra batalhas do ano ou retorna todas
        filtered_battles = self.filter_battles_by_year(battles, year, all_battles)
        
        if all_battles:
            print(f"Processando todas as {len(filtered_battles)} batalhas disponiveis...")
        else:
            print(f"Batalhas do ano {year}: {len(filtered_battles)}")
        
        if not filtered_battles:
            if all_battles:
                print("Nenhuma batalha encontrada.")
            else:
                print(f"Nenhuma batalha encontrada para o ano {year}.")
            return
        
        # Extrai informacoes dos oponentes
        opponents_data = []
        for battle in filtered_battles:
            opponent_info = self.extract_opponent_info(battle, player_tag)
            if opponent_info:
                # Adiciona informacoes do deck
                teams = battle.get('team', [])
                player_team = None
                for team in teams:
                    if team.get('tag') == player_tag:
                        player_team = team
                        break
                
                opponent_info['deck_jogador'] = self.format_deck(player_team.get('cards', [])) if player_team else ''
                
                opponents = battle.get('opponent', [])
                opponent_team = opponents[0] if opponents else None
                opponent_info['deck_oponente'] = self.format_deck(opponent_team.get('cards', [])) if opponent_team else ''
                
                opponents_data.append(opponent_info)
        
        # Conta repeticoes
        opponent_tags = [op['tag_oponente'] for op in opponents_data if op['tag_oponente']]
        opponent_counts = Counter(opponent_tags)
        
        # Adiciona contador de repeticoes a cada linha
        for opponent_info in opponents_data:
            tag = opponent_info['tag_oponente']
            count = opponent_counts.get(tag, 0)
            opponent_info['vezes_enfrentado'] = count
        
        # Ordena por data (mais recente primeiro)
        opponents_data.sort(key=lambda x: x['data'], reverse=True)
        
        # Gera CSV
        fieldnames = [
            'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente', 
            'trofes_oponente', 'clan_oponente', 'resultado', 
            'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
            'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente', 'vezes_enfrentado'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(opponents_data)
        
        print(f"\nRelatorio gerado: {output_file}")
        print(f"Total de oponentes unicos: {len(opponent_counts)}")
        print(f"Total de batalhas registradas: {len(opponents_data)}")
        
        # Mostra oponentes repetidos
        repeated = {tag: count for tag, count in opponent_counts.items() if count > 1}
        if repeated:
            print(f"\nOponentes enfrentados mais de uma vez ({len(repeated)}):")
            sorted_repeated = sorted(repeated.items(), key=lambda x: x[1], reverse=True)
            for tag, count in sorted_repeated[:10]:  # Top 10
                # Busca nome do oponente
                opponent_name = next((op['nome_oponente'] for op in opponents_data if op['tag_oponente'] == tag), tag)
                print(f"  - {opponent_name} ({tag}): {count} vezes")
        else:
            print("\nNenhum oponente foi enfrentado mais de uma vez no periodo.")

def main():
    """Funcao principal"""
    parser = argparse.ArgumentParser(
        description='Gera relatorio CSV dos oponentes enfrentados no Clash Royale'
    )
    parser.add_argument(
        '--ano', 
        type=int, 
        default=None,
        help='Ano para filtrar batalhas (padrao: ano atual). Use --todos para todas as batalhas disponiveis'
    )
    parser.add_argument(
        '--todos',
        action='store_true',
        help='Buscar todas as batalhas disponiveis (sem filtro de ano)'
    )
    parser.add_argument(
        '--arquivo', 
        type=str, 
        default=None,
        help='Nome do arquivo CSV de saida (padrao: oponentes_YYYY.csv)'
    )
    parser.add_argument(
        '--token',
        type=str,
        default=None,
        help='Token da API (ou use variavel de ambiente CR_API_TOKEN)'
    )
    parser.add_argument(
        '--tag',
        type=str,
        default=None,
        help='Tag do jogador (ou use variavel de ambiente CR_PLAYER_TAG)'
    )
    parser.add_argument(
        '--salvar-banco',
        action='store_true',
        help='Salvar batalhas no banco de dados (acumula dados)'
    )
    parser.add_argument(
        '--do-banco',
        action='store_true',
        help='Gerar CSV a partir do banco de dados (dados acumulados)'
    )
    parser.add_argument(
        '--banco',
        type=str,
        default='oponentes.db',
        help='Caminho do arquivo do banco de dados (padrao: oponentes.db)'
    )
    parser.add_argument(
        '--periodos',
        action='store_true',
        help='Gera CSVs para dia, semana, mes e ano atual (acumulados do banco)'
    )
    
    args = parser.parse_args()
    
    # Busca token da API
    API_TOKEN = args.token or os.getenv("CR_API_TOKEN")
    PLAYER_TAG = args.tag or os.getenv("CR_PLAYER_TAG")
    
    if not API_TOKEN:
        print("Erro: Token da API nao configurado")
        print("Use --token ou configure a variavel de ambiente CR_API_TOKEN")
        sys.exit(1)
    
    if not PLAYER_TAG:
        print("Erro: Tag do jogador nao configurada")
        print("Use --tag ou configure a variavel de ambiente CR_PLAYER_TAG")
        sys.exit(1)
    
    # Determina se busca todas as batalhas ou filtra por ano
    all_battles = args.todos
    
    if all_battles:
        year_label = "Todas as batalhas disponiveis"
        output_file = args.arquivo or "oponentes_todos.csv"
    else:
        year = args.ano or datetime.now().year
        year_label = f"Ano: {year}"
        output_file = args.arquivo or f"oponentes_{year}.csv"
    
    print("=" * 60)
    print("Relatorio de Oponentes - Clash Royale")
    print("=" * 60)
    print(f"Jogador: {PLAYER_TAG}")
    print(f"{year_label}")
    print(f"Arquivo de saida: {output_file}")
    print("=" * 60)
    
    # Gera relatorio
    reporter = OpponentsReporter(API_TOKEN, db_path=args.banco)
    
    # Se gerar por periodos (dia, semana, mes, ano)
    if args.periodos:
        print("=" * 60)
        print("Gerando CSVs por periodo (dia, semana, mes, ano)")
        print("=" * 60)
        arquivos = reporter.generate_period_csvs(PLAYER_TAG)
        print(f"\nTotal de arquivos gerados: {len(arquivos)}")
        for arquivo in arquivos:
            print(f"  - {arquivo}")
    # Se gerar do banco, usa dados acumulados
    elif args.do_banco:
        if all_battles:
            reporter.generate_csv_from_db(PLAYER_TAG, output_file=output_file, all_battles=True)
        else:
            reporter.generate_csv_from_db(PLAYER_TAG, year=year, output_file=output_file, all_battles=False)
    else:
        # Gera da API e opcionalmente salva no banco
        save_to_db = args.salvar_banco
        if all_battles:
            reporter.generate_csv_report(PLAYER_TAG, output_file=output_file, all_battles=True, save_to_db=save_to_db)
        else:
            reporter.generate_csv_report(PLAYER_TAG, year=year, output_file=output_file, all_battles=False, save_to_db=save_to_db)

if __name__ == "__main__":
    main()

