import json
import pandas as pd
from datetime import datetime, timedelta

def format_date_brt(battle_time_str):
    try:
        # Formato API: 20260504T003615.000Z
        dt_utc = datetime.strptime(battle_time_str[:15], '%Y%m%dT%H%M%S')
        # Ajuste para BRT (UTC-3)
        dt_brt = dt_utc - timedelta(hours=3)
        return dt_brt.strftime('%d/%m/%Y %H:%M')
    except:
        return ""

def process_json_recovery():
    json_path = "src/data_csv_oficial/recuperacao_raw_api.json"
    output_path = "src/data_csv_oficial/extracao_especifica_maio_2026_FINAL.csv"
    
    print(f"Lendo JSON de recuperação: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        battles = json.load(f)
    
    target_dates = ["30/04/2026", "01/05/2026", "02/05/2026", "03/05/2026"]
    extracted_data = []
    
    for b in battles:
        b_date = format_date_brt(b.get('battleTime', ''))
        
        # Filtro por data
        if any(d in b_date for d in target_dates):
            team = b.get('team', [{}])[0]
            opponent = b.get('opponent', [{}])[0]
            
            # Extração dos campos solicitados
            nivel_rei = team.get('expLevel', 'N/A')
            rei_jogador = team.get('kingTowerHitPoints', 'N/A')
            rei_oponente = opponent.get('kingTowerHitPoints', 'N/A')
            
            princesas_jogador = team.get('princessTowersHitPoints', [])
            princesas_oponente = opponent.get('princessTowersHitPoints', [])
            
            # Formatação conforme padrão do CSV: "HP1 | HP2"
            pj_str = " | ".join(map(str, princesas_jogador)) if princesas_jogador else "N/A"
            po_str = " | ".join(map(str, princesas_oponente)) if princesas_oponente else "N/A"
            
            row = {
                'data': b_date,
                'nome_oponente': opponent.get('name', 'N/A'),
                'tag_oponente': opponent.get('tag', 'N/A'),
                'resultado': 'Vitoria' if team.get('crowns', 0) > opponent.get('crowns', 0) else 'Derrota' if team.get('crowns', 0) < opponent.get('crowns', 0) else 'Empate',
                'nivel_torre_jogador': nivel_rei,
                'vida_torre_rei_jogador': rei_jogador,
                'vida_torre_rei_oponente': rei_oponente,
                'vida_torres_princesa_jogador': pj_str,
                'vida_torres_princesa_oponente': po_str
            }
            extracted_data.append(row)
    
    if extracted_data:
        df = pd.DataFrame(extracted_data)
        # Ordenar por data (mais recente primeiro como no CSV oficial)
        df['dt_obj'] = pd.to_datetime(df['data'], format='%d/%m/%Y %H:%M')
        df = df.sort_values(by='dt_obj', ascending=False).drop(columns=['dt_obj'])
        
        df.to_csv(output_path, index=False, sep=';', encoding='utf-8')
        print(f"Sucesso! {len(df)} batalhas salvas em: {output_path}")
        return True
    else:
        print("Nenhuma batalha encontrada para as datas solicitadas dentro do JSON.")
        return False

if __name__ == "__main__":
    process_json_recovery()
