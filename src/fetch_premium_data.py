import os
import requests
import csv
from datetime import datetime

def fetch_premium_data():
    # Carrega variáveis do ambiente se disponíveis
    player_tag = os.getenv('CR_PLAYER_TAG', '#2QR292P').replace('#', '%23')
    api_token = os.getenv('CR_API_TOKEN')
    
    if not api_token:
        # Tenta pegar de um arquivo .env se existir (opcional)
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
    dates_to_update = ['20260430', '20260501', '20260502']
    csv_dir = "src/data_csv_oficial"
    
    for date_str in dates_to_update:
        file_path = os.path.join(csv_dir, f"oponentes_dia_{date_str}.csv")
        if not os.path.exists(file_path):
            continue
            
        print(f"Verificando {file_path}...")
        
        # Ler arquivo atual
        rows = []
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content_sample = f.read(100)
                delim = ';' if ';' in content_sample else ','
                f.seek(0)
                reader = csv.DictReader(f, delimiter=delim)
                rows = list(reader)
                fieldnames = reader.fieldnames
        except Exception as e:
            print(f"Erro ao ler {file_path}: {e}")
            continue

        updated_count = 0
        for row in rows:
            row_time_raw = row.get('data')
            if not row_time_raw: continue
            
            try:
                dt_obj = datetime.strptime(row_time_raw, "%d/%m/%Y %H:%M")
                row_time_comp = dt_obj.strftime("%Y%m%dT%H%M")
            except:
                continue

            for b in battles:
                b_time_api = b.get('battleTime', '').replace('.000Z', '')
                if b_time_api.startswith(row_time_comp):
                    updated_count += 1
                    
                    # Elixir
                    row['elixir_vazado_jogador'] = b.get('team', [{}])[0].get('elixirLeaked', row.get('elixir_vazado_jogador', '0'))
                    row['elixir_vazado_oponente'] = b.get('opponent', [{}])[0].get('elixirLeaked', row.get('elixir_vazado_oponente', '0'))
                    
                    # Nível Torre
                    row['nivel_torre_jogador'] = b.get('team', [{}])[0].get('level', row.get('nivel_torre_jogador', '0'))
                    row['nivel_torre_oponente'] = b.get('opponent', [{}])[0].get('level', row.get('nivel_torre_oponente', '0'))
                    
                    # Troféus
                    start_t = b.get('team', [{}])[0].get('startingTrophies')
                    change_t = b.get('team', [{}])[0].get('trophyChange')
                    
                    if start_t is not None:
                        row['trofes_iniciais_jogador'] = start_t
                        if change_t is not None:
                            row['trofes_finais_jogador'] = start_t + change_t
                    
                    # Posição Global
                    row['posicao_global_jogador'] = b.get('team', [{}])[0].get('globalRank', row.get('posicao_global_jogador', 'N/A'))
                    row['posicao_global_oponente'] = b.get('opponent', [{}])[0].get('globalRank', row.get('posicao_global_oponente', 'N/A'))
                    break
        
        if updated_count > 0:
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
                writer.writeheader()
                writer.writerows(rows)
            print(f"  {updated_count} batalhas atualizadas em {file_path}")

if __name__ == "__main__":
    fetch_premium_data()
