import os
import sys
import requests
import csv
import glob
from datetime import datetime
from dotenv import load_dotenv

# Forçar UTF-8 apenas se não estiver configurado
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

def get_config():
    token = os.getenv('CR_API_TOKEN')
    headers = {'Authorization': f'Bearer {token}'}
    base_url = "https://proxy.royaleapi.dev/v1"
    # Conta principal
    clan_tag_pri = "%23QCLPL9VQ"
    # Conta secundária
    clan_tag_sec = "%23R0JVY98R"
    return headers, base_url, clan_tag_pri, clan_tag_sec

script_dir = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(script_dir, 'data_clan')

def collect_boat_data_for_clan(headers, base_url, clan_tag, suffix=""):
    """Coleta status dos barcos para um clã específico."""
    r = requests.get(f"{base_url}/clans/{clan_tag}/currentriverrace", headers=headers, timeout=15)
    
    if r.status_code == 200:
        data = r.json()
        clans = data.get('clans', [])
        
        os.makedirs(DATA_DIR, exist_ok=True)
        today = datetime.now().strftime('%Y_%m_%d')
        filename = os.path.join(DATA_DIR, f'status_barcos{suffix}_{today}.csv')
        
        # Verificar se dados atuais estão vazios
        total_fame = sum(c.get('fame', 0) for c in clans)
        
        if total_fame == 0:
            # Buscar arquivo anterior com dados (excluindo o proprio de hoje)
            pattern = os.path.join(DATA_DIR, f'status_barcos{suffix}_*.csv')
            previous_files = [f for f in glob.glob(pattern) if os.path.abspath(f) != os.path.abspath(filename)]
            previous_files = sorted(previous_files)
            if previous_files:
                latest_existing = max(previous_files)
                print(f"Aviso: Dados vazios. Mantendo arquivo anterior: {os.path.basename(latest_existing)}")
                import shutil
                shutil.copy(latest_existing, filename)
                return filename
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Posicao', 'Nome_Cla', 'Fama_Atual', 'Pontos_Reparo', 'Finalizado', 'Pontos_Periodo'])
            
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
        
        print(f"SUCESSO: status_barcos{suffix}_{today}.csv")
        return filename
    else:
        print(f"Erro ao buscar dados da corrida: {r.status_code}")
        return None

def collect_boat_data():
    headers, base_url, clan_tag_pri, clan_tag_sec = get_config()
    
    print("=" * 60)
    print("COLETANDO STATUS BARCOS - AMBAS CONTAS")
    print("=" * 60)
    
    print("\n--- CONTA PRINCIPAL ---")
    filename_pri = collect_boat_data_for_clan(headers, base_url, clan_tag_pri, '_pri')
    
    print("\n--- CONTA SECUNDARIA ---")
    filename_sec = collect_boat_data_for_clan(headers, base_url, clan_tag_sec, '_sec')
    
    # Se algum arquivo não foi criado por falta de dados, copiar do anterior
    if not filename_pri or not os.path.exists(filename_pri):
        filename = os.path.join(DATA_DIR, f'status_barcos_pri_{datetime.now().strftime("%Y_%m_%d")}.csv')
        pattern = os.path.join(DATA_DIR, 'status_barcos_pri_*.csv')
        previous = [f for f in glob.glob(pattern) if os.path.abspath(f) != os.path.abspath(filename)]
        if previous:
            import shutil
            shutil.copy(max(previous), filename)
            print(f"Copiado status_barcos_pri do dia anterior")
    
    if not filename_sec or not os.path.exists(filename_sec):
        filename = os.path.join(DATA_DIR, f'status_barcos_sec_{datetime.now().strftime("%Y_%m_%d")}.csv')
        pattern = os.path.join(DATA_DIR, 'status_barcos_sec_*.csv')
        previous = [f for f in glob.glob(pattern) if os.path.abspath(f) != os.path.abspath(filename)]
        if previous:
            import shutil
            shutil.copy(max(previous), filename)
            print(f"Copiado status_barcos_sec do dia anterior")
    
    print("\n" + "=" * 60)
    print("COLETA DE STATUS BARCOS CONCLUIDA")
    print("=" * 60)

if __name__ == "__main__":
    collect_boat_data()
