import os
import requests
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

FIELDNAMES = [
    'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente',
    'trofes_oponente', 'clan_oponente', 'resultado',
    'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
    'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente', 'vezes_enfrentado',
    'elixir_vazado_jogador', 'elixir_vazado_oponente', 'nivel_torre_jogador',
    'vida_torre_rei_jogador', 'vida_torre_rei_oponente', 
    'vida_torres_princesa_jogador', 'vida_torres_princesa_oponente',
    'trofes_iniciais_jogador', 'trofes_finais_jogador',
    'posicao_global_jogador', 'posicao_global_oponente', 'nivel_torre_oponente'
]

DATA_DIR = 'src/data_csv_oficial'

def format_date_brt(battle_time_str):
    try:
        dt_utc = datetime.strptime(battle_time_str[:15], '%Y%m%dT%H%M%S')
        return (dt_utc - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')
    except:
        return ""

def format_hp(hp_list):
    if hp_list is None: return "0"
    if isinstance(hp_list, int): return str(hp_list)
    return " | ".join(map(str, hp_list))

def enrich():
    token = os.getenv('CR_API_TOKEN')
    tag = os.getenv('CR_PLAYER_TAG')
    if not token or not tag:
        print("Erro: Credenciais nao encontradas.")
        return

    print(f"Buscando log da API para o jogador {tag}...")
    tag_url = tag.replace('#', '%23')
    r = requests.get(f"https://proxy.royaleapi.dev/v1/players/{tag_url}/battlelog", headers={'Authorization': f'Bearer {token}'})
    
    if r.status_code != 200:
        print(f"Erro na API: {r.status_code}")
        return

    battles = r.json()
    print(f"Encontradas {len(battles)} batalhas no log da API.")

    # Mapear batalhas da API por (data_brt, tag_oponente)
    api_map = {}
    for b in battles:
        data_brt = format_date_brt(b.get('battleTime', ''))
        opp_tag = b.get('opponent', [{}])[0].get('tag', '')
        if data_brt and opp_tag:
            api_map[(data_brt, opp_tag)] = b

    # Percorrer arquivos CSV para atualizar
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.csv'):
            file_path = os.path.join(DATA_DIR, filename)
            rows = []
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    rows = list(reader)
                
                if not rows: continue

                updated_count = 0
                for row in rows:
                    key = (row.get('data', ''), row.get('tag_oponente', ''))
                    if key in api_map:
                        b = api_map[key]
                        # Encontra o time do jogador e oponente
                        teams = b.get('team', [])
                        player_team = next((t for t in teams if t.get('tag') == tag), None)
                        opponents = b.get('opponent', [])
                        opponent_team = opponents[0] if opponents else None
                        
                        if player_team and opponent_team:
                            # Atualiza campos detalhados
                            row['elixir_vazado_jogador'] = round(player_team.get('elixirLeaked', 0), 2)
                            row['elixir_vazado_oponente'] = round(opponent_team.get('elixirLeaked', 0), 2)
                            row['vida_torre_rei_jogador'] = player_team.get('kingTowerHitPoints', 0)
                            row['vida_torre_rei_oponente'] = opponent_team.get('kingTowerHitPoints', 0)
                            row['vida_torres_princesa_jogador'] = format_hp(player_team.get('princessTowersHitPoints'))
                            row['vida_torres_princesa_oponente'] = format_hp(opponent_team.get('princessTowersHitPoints'))
                            row['trofes_iniciais_jogador'] = player_team.get('startingTrophies', 0)
                            row['trofes_finais_jogador'] = player_team.get('startingTrophies', 0) + player_team.get('trophyChange', 0)
                            row['posicao_global_jogador'] = player_team.get('globalRank', 'N/A') or 'N/A'
                            row['posicao_global_oponente'] = opponent_team.get('globalRank', 'N/A') or 'N/A'
                            row['nivel_torre_oponente'] = opponent_team.get('expLevel', 0)
                            updated_count += 1

                if updated_count > 0:
                    with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=';', extrasaction='ignore')
                        writer.writeheader()
                        writer.writerows(rows)
                    print(f"  {filename}: {updated_count} batalhas enriquecidas.")
            except Exception as e:
                print(f"  Erro ao processar {filename}: {e}")

if __name__ == "__main__":
    enrich()
