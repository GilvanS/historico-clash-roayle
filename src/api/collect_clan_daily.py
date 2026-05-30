import os
import requests
import csv
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def get_config():
    token = os.getenv('CR_API_TOKEN')
    headers = {'Authorization': f'Bearer {token}'}
    base_url = "https://proxy.royaleapi.dev/v1"
    clan_tag = "%23QCLPL9VQ"
    return headers, base_url, clan_tag

def format_date(timestamp_str):
    # Converte formato Supercell (20260501T123000.000Z) para BRT
    try:
        dt = datetime.strptime(timestamp_str, '%Y%m%dT%H%M%S.%fZ')
        return dt.strftime('%d/%m/%Y %H:%M')
    except:
        return timestamp_str

def collect_data():
    headers, base_url, clan_tag = get_config()
    os.makedirs('data/csv', exist_ok=True)
    today = datetime.now().strftime('%Y_%m_%d')

    # 1. Coleta Membros (Doações e Atividade)
    r_members = requests.get(f"{base_url}/clans/{clan_tag}/members", headers=headers)
    if r_members.status_code == 200:
        members = r_members.json().get('items', [])
        filename = f'data/csv/membros_stats_{today}.csv'
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Nome', 'Cargo', 'Trofeus', 'Doacoes_Feitas', 'Doacoes_Recebidas', 'Ultimo_Acesso'])
            for m in members:
                writer.writerow([
                    m.get('name'),
                    m.get('role'),
                    m.get('trophies'),
                    m.get('donations'),
                    m.get('donationsReceived'),
                    format_date(m.get('lastSeen'))
                ])
        print(f"SUCESSO: Arquivo de membros gerado: {filename}")

    # 2. Coleta Guerra (Ataques e Fama)
    r_war = requests.get(f"{base_url}/clans/{clan_tag}/currentriverrace", headers=headers)
    if r_war.status_code == 200:
        war_data = r_war.json()
        participants = war_data.get('clan', {}).get('participants', [])
        filename_war = f'data/csv/guerra_stats_{today}.csv'
        with open(filename_war, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Nome', 'Tag', 'Fama_Contribuida', 'Pontos_Reparo', 'Decks_Usados'])
            for p in participants:
                # Na API, decks usados = ataques totais divididos por 1 (cada ataque é um deck)
                # O campo costuma ser decksUsed ou calculado pela fama
                writer.writerow([
                    p.get('name'),
                    p.get('tag'),
                    p.get('fame'),
                    p.get('repairPoints'),
                    p.get('decksUsedToday', 0)
                ])
        print(f"SUCESSO: Arquivo de guerra gerado: {filename_war}")

if __name__ == "__main__":
    collect_data()
