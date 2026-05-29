import os
import requests
import csv
from datetime import datetime, timedelta

def fetch_premium_data():
    player_tag = os.getenv('CR_PLAYER_TAG', '#2QR292P').replace('#', '%23')
    api_token = os.getenv('CR_API_TOKEN')
    
    if not api_token:
        print("Erro: CR_API_TOKEN não configurado no ambiente.")
        return

    url = f"https://proxy.royaleapi.dev/v1/players/{player_tag}/battlelog"
    headers = {"Authorization": f"Bearer {api_token}"}
    
    print(f"Buscando histórico de batalhas para {player_tag}...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Erro na API: {response.status_code}")
            return
    except Exception as e:
        print(f"Erro na requisição: {e}")
        return

    battles = response.json()
    print(f"Recebidas {len(battles)} batalhas da API.")

    # Mapeamento de arquivos para atualizar
    csv_dir = "data/csv"
    dates_to_update = [f.split('_')[-1].split('.')[0] for f in os.listdir(csv_dir) if f.startswith("oponentes_dia_") and f.endswith(".csv")]
    dates_to_update.sort(reverse=True)
    
    for date_str in dates_to_update:
        file_path = os.path.join(csv_dir, f"oponentes_dia_{date_str}.csv")
        if not os.path.exists(file_path):
            continue
            
        print(f"Verificando {file_path}...")
        
        rows = []
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                rows = list(reader)
                fieldnames = reader.fieldnames
        except Exception as e:
            print(f"Erro ao ler {file_path}: {e}")
            continue

        updated_count = 0
        for row in rows:
            row_opp_tag = row.get('tag_oponente', '').strip().replace('#', '')
            row_date_raw = row.get('data', '').split(' ')[0] # DD/MM/YYYY
            
            for b in battles:
                b_opp_tag = b.get('opponent', [{}])[0].get('tag', '').replace('#', '')
                b_time_api = b.get('battleTime', '') # YYYYMMDDTHHMMSS.000Z
                
                # Converter data da API para DD/MM/YYYY (UTC-3 aproximado)
                try:
                    b_dt_utc = datetime.strptime(b_time_api[:15], "%Y%m%dT%H%M%S")
                    b_dt_brt = b_dt_utc - timedelta(hours=3)
                    b_date_brt = b_dt_brt.strftime("%d/%m/%Y")
                except:
                    continue

                # Se a tag bater e a data bater (ou for dia anterior/próximo devido a fuso)
                if b_opp_tag == row_opp_tag and (b_date_brt == row_date_raw):
                    updated_count += 1
                    team = b.get('team', [{}])[0]
                    opponent = b.get('opponent', [{}])[0]
                    
                    row['elixir_vazado_jogador'] = team.get('elixirLeaked', row.get('elixir_vazado_jogador', '0'))
                    row['elixir_vazado_oponente'] = opponent.get('elixirLeaked', row.get('elixir_vazado_oponente', '0'))
                    row['nivel_torre_jogador'] = team.get('level', row.get('nivel_torre_jogador', '0'))
                    row['nivel_torre_oponente'] = opponent.get('level', row.get('nivel_torre_oponente', '0'))
                    
                    # HP das Torres
                    row['vida_torre_rei_jogador'] = team.get('kingTowerHitPoints', row.get('vida_torre_rei_jogador', '0'))
                    row['vida_torre_rei_oponente'] = opponent.get('kingTowerHitPoints', row.get('vida_torre_rei_oponente', '0'))
                    
                    p_hps_j = team.get('princessTowersHitPoints', [])
                    p_hps_o = opponent.get('princessTowersHitPoints', [])
                    if p_hps_j: row['vida_torres_princesa_jogador'] = " | ".join(map(str, p_hps_j))
                    if p_hps_o: row['vida_torres_princesa_oponente'] = " | ".join(map(str, p_hps_o))

                    # Troféus
                    start_t = team.get('startingTrophies')
                    change_t = team.get('trophyChange')
                    if start_t is not None:
                        row['trofes_iniciais_jogador'] = start_t
                        if change_t is not None:
                            row['trofes_finais_jogador'] = start_t + change_t
                    
                    # Posição Global
                    row['posicao_global_jogador'] = team.get('globalRank', row.get('posicao_global_jogador', 'N/A'))
                    row['posicao_global_oponente'] = opponent.get('globalRank', row.get('posicao_global_oponente', 'N/A'))
                    break
        
        if updated_count > 0:
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
                writer.writeheader()
                writer.writerows(rows)
            print(f"  {updated_count} batalhas atualizadas em {file_path}")

if __name__ == "__main__":
    fetch_premium_data()
