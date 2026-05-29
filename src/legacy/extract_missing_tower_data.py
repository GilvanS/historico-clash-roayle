import requests
import os
import pandas as pd
from datetime import datetime
import time

def load_env():
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    value = value.strip('"').strip("'")
                    # Só carrega se não estiver definido ou se for um placeholder
                    if key not in os.environ or os.environ[key] == key:
                        os.environ[key] = value

def format_date(api_date):
    # API format: 20260504T003615.000Z
    dt = datetime.strptime(api_date, '%Y%m%dT%H%M%S.%f%z')
    return dt.strftime('%d/%m/%Y %H:%M')

def extract_data():
    load_env()
    token = os.getenv('CR_API_TOKEN')
    # Tentar as duas tags conhecidas
    tags = [os.getenv('CR_PLAYER_TAG', '#2QR292P'), '#2B2Y0R80']
    
    target_dates = ['20260430', '20260501', '20260502', '20260503']
    all_battles = []
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    for tag in tags:
        tag_clean = tag.replace("#", "").upper()
        print(f"Consultando log via PROXY para a tag: #{tag_clean}...")
        # Usando o proxy RoyaleAPI que ja esta mapeado no seu projeto para evitar erro 403
        url = f"https://proxy.royaleapi.dev/v1/players/%23{tag_clean}/battlelog"
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                log = response.json()
                print(f"Encontradas {len(log)} batalhas no log.")
                
                for battle in log:
                    battle_time = battle.get('battleTime', '')
                    date_part = battle_time[:8]
                    
                    if date_part in target_dates:
                        team = battle.get('team', [{}])[0]
                        opponent = battle.get('opponent', [{}])[0]
                        
                        # Extração segura dos dados de torre
                        # Nota: A API nem sempre retorna esses campos se a torre não foi atingida ou dependendo do modo
                        
                        # No CSV do usuário, parece que 'nivel_torre_jogador' pode ser o nível do Rei
                        nivel_rei = team.get('expLevel', 'N/A')
                        
                        # Hitpoints (se disponível)
                        rei_jogador = team.get('kingTowerHitPoints', 'N/A')
                        rei_oponente = opponent.get('kingTowerHitPoints', 'N/A')
                        
                        princesas_jogador = team.get('princessTowersHitPoints', [])
                        princesas_oponente = opponent.get('princessTowersHitPoints', [])
                        
                        # Formatar como no CSV: "HP1 | HP2"
                        pj_str = " | ".join(map(str, princesas_jogador)) if princesas_jogador else "N/A"
                        po_str = " | ".join(map(str, princesas_oponente)) if princesas_oponente else "N/A"
                        
                        battle_data = {
                            'data': format_date(battle_time),
                            'nome_oponente': opponent.get('name', 'N/A'),
                            'tag_oponente': opponent.get('tag', 'N/A'),
                            'resultado': 'Vitoria' if team.get('crowns', 0) > opponent.get('crowns', 0) else 'Derrota' if team.get('crowns', 0) < opponent.get('crowns', 0) else 'Empate',
                            'nivel_torre_jogador': nivel_rei,
                            'vida_torre_rei_jogador': rei_jogador,
                            'vida_torre_rei_oponente': rei_oponente,
                            'vida_torres_princesa_jogador': pj_str,
                            'vida_torres_princesa_oponente': po_str
                        }
                        all_battles.append(battle_data)
            else:
                print(f"Erro ao consultar {tag}: {response.status_code}")
        except Exception as e:
            print(f"Falha na conexão para {tag}: {e}")

    if all_battles:
        df = pd.DataFrame(all_battles)
        # Remover duplicatas baseadas na data e oponente
        df = df.drop_duplicates(subset=['data', 'tag_oponente'])
        
        output_path = "data/csv/extracao_especifica_abril_maio_2026.csv"
        df.to_csv(output_path, index=False, sep=';', encoding='utf-8')
        print(f"\nSUCESSO! {len(df)} batalhas extraídas para o arquivo: {output_path}")
    else:
        print("\nAVISO: Nenhuma batalha encontrada para as datas alvo no log atual.")
        print("Dica: A API só guarda as últimas 25-30 batalhas. Se você jogou muito desde o dia 03/05, esses dados podem ter expirado no log da API.")

if __name__ == "__main__":
    extract_data()
