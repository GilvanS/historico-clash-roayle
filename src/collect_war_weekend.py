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

def collect_boat_data():
    # Verifica se hoje é entre Quinta (3) e Domingo (6)
    # 0=Segunda, 1=Terca, 2=Quarta, 3=Quinta, 4=Sexta, 5=Sabado, 6=Domingo
    weekday = datetime.now().weekday()
    is_war_day = weekday >= 3 

    if not is_war_day:
        print("Hoje não é dia de guerra ativa (Quinta a Domingo).")
        # Mesmo assim vamos coletar se o usuário pediu manualmente
    
    headers, base_url, clan_tag = get_config()
    r = requests.get(f"{base_url}/clans/{clan_tag}/currentriverrace", headers=headers)
    
    if r.status_code == 200:
        data = r.json()
        clans = data.get('clans', [])
        today = datetime.now().strftime('%Y_%m_%d')
        
        os.makedirs('src/data_clan', exist_ok=True)
        filename = f'src/data_clan/status_barcos_{today}.csv'
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Posicao', 'Nome_Cla', 'Fama_Atual', 'Pontos_Reparo', 'Finalizado', 'Pontos_Periodo'])
            
            # Ordena os clãs pela fama (quem está na frente)
            sorted_clans = sorted(clans, key=lambda x: x.get('fame', 0), reverse=True)
            
            for i, clan in enumerate(sorted_clans):
                writer.writerow([
                    i + 1,
                    clan.get('name'),
                    clan.get('fame'),
                    clan.get('repairPoints'),
                    "Sim" if clan.get('finishTime') else "Não",
                    clan.get('periodPoints')
                ])
        
        print(f"SUCESSO: Relatório dos barcos gerado: {filename}")
        
        # Exibe um resumo no terminal
        print("\n=== POSIÇÃO DA CORRIDA AGORA ===")
        for i, c in enumerate(sorted_clans):
            print(f"{i+1}º - {c.get('name'):<20} | Fama: {c.get('fame'):<6} | Pontos: {c.get('periodPoints')}")
    else:
        print(f"Erro ao buscar dados da corrida: {r.status_code}")

if __name__ == "__main__":
    collect_boat_data()
