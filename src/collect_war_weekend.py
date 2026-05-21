import os
import sys
import requests
import csv
import glob
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Forcar UTF-8 apenas se nao estiver configurado
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
    # Conta secundaria
    clan_tag_sec = "%23R0JVY98R"
    return headers, base_url, clan_tag_pri, clan_tag_sec

script_dir = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(script_dir, 'data_clan')

def get_logical_date_and_battle_day():
    """Retorna data coleta logica e dia batalha com base no reset pontual das 07:00:00 da manha."""
    now = datetime.now()
    if now.hour < 7:
        logical_date = now - timedelta(days=1)
    else:
        logical_date = now
    
    data_str = logical_date.strftime('%Y-%m-%d')
    wd = logical_date.weekday()
    
    # Quinta=Dia 1 (3), Sexta=Dia 2 (4), Sabado=Dia 3 (5), Domingo=Dia 4 (6), Reset=Segunda em diante
    if wd == 3:
        dia_batalha = 'Dia 1'
    elif wd == 4:
        dia_batalha = 'Dia 2'
    elif wd == 5:
        dia_batalha = 'Dia 3'
    elif wd == 6:
        dia_batalha = 'Dia 4'
    else:
        dia_batalha = 'Reset'
        
    return data_str, dia_batalha

def collect_boat_data_for_clan(headers, base_url, clan_tag, suffix=""):
    """Coleta status dos barcos para um clan especifico e insere no status_barcos_historico.csv."""
    r = requests.get(f"{base_url}/clans/{clan_tag}/currentriverrace", headers=headers, timeout=15)
    
    data_hoje, dia_batalha = get_logical_date_and_battle_day()
    conta_tipo = 'principal' if suffix == '_pri' else 'secundaria'
    
    historico_path = os.path.join(DATA_DIR, 'status_barcos_historico.csv')
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Lista para novos registros coletados nesta rodada
    new_records = []
    
    if r.status_code == 200:
        data = r.json()
        clans = data.get('clans', [])
        
        # Verificar se dados atuais estao vazios (fama total zerada)
        total_fame = sum(c.get('fame', 0) for c in clans)
        
        if total_fame == 0:
            print(f"Aviso: Fama total zerada. Tentando buscar fallback do historico...")
            new_records = get_fallback_from_history(historico_path, conta_tipo, data_hoje, dia_batalha)
        else:
            sorted_clans = sorted(clans, key=lambda x: x.get('fame', 0), reverse=True)
            for i, clan in enumerate(sorted_clans):
                new_records.append({
                    'data_coleta': data_hoje,
                    'dia_batalha': dia_batalha,
                    'conta_tipo': conta_tipo,
                    'posicao': i + 1,
                    'clan_nome': clan.get('name'),
                    'clan_tag': clan.get('tag'),
                    'fama_atual': clan.get('fame'),
                    'pontos_reparo': clan.get('repairPoints'),
                    'finalizado': "Sim" if clan.get('finishTime') else "Não",
                    'pontos_periodo': clan.get('periodPoints')
                })
    else:
        print(f"Erro ao buscar dados da corrida (Status: {r.status_code}). Tentando fallback do historico...")
        new_records = get_fallback_from_history(historico_path, conta_tipo, data_hoje, dia_batalha)
        
    if not new_records:
        print(f"ERRO: Nao foi possivel obter dados reais nem fallback para {conta_tipo}!")
        return None
        
    # Carregar registros existentes de status_barcos_historico.csv para aplicar idempotencia
    existing_records = []
    if os.path.exists(historico_path):
        try:
            with open(historico_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    # Idempotencia: remover registros antigos da mesma data_coleta e conta_tipo
                    if row.get('data_coleta') == data_hoje and row.get('conta_tipo') == conta_tipo:
                        continue
                    existing_records.append(row)
        except Exception as e:
            print(f"Aviso: Erro ao ler status_barcos_historico.csv para idempotencia: {e}")
            
    # Concatenar todos os registros e gravar de volta
    final_records = existing_records + new_records
    
    # Ordenar registros finais por data decrescente, conta_tipo e posicao crescente
    final_records = sorted(
        final_records,
        key=lambda x: (x['data_coleta'], x.get('conta_tipo', ''), int(x.get('posicao', 1) or 1)),
        reverse=True
    )
    
    # Gravar no status_barcos_historico.csv consolidado
    fieldnames = ['data_coleta', 'dia_batalha', 'conta_tipo', 'posicao', 'clan_nome', 'clan_tag', 'fama_atual', 'pontos_reparo', 'finalizado', 'pontos_periodo']
    try:
        with open(historico_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(final_records)
        print(f"SUCESSO: status_barcos_historico.csv atualizado de forma idempotente para {conta_tipo} ({len(new_records)} novos, {len(final_records)} total)")
    except Exception as e:
        print(f"ERRO ao gravar status_barcos_historico.csv: {e}")
        
    # Salvar tambem uma copia diaria de backup legada para compatibilidade de outros scripts
    # Nome esperado legado: status_barcos_pri_2026_05_21.csv (com sub-tracos)
    today_sub = data_hoje.replace('-', '_')
    legacy_filename = os.path.join(DATA_DIR, f'status_barcos{suffix}_{today_sub}.csv')
    try:
        with open(legacy_filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Posicao', 'Nome_Cla', 'Fama_Atual', 'Pontos_Reparo', 'Finalizado', 'Pontos_Periodo'])
            
            # Filtra e ordena registros apenas do dia de hoje para o arquivo diário
            today_records = [r for r in new_records if r['data_coleta'] == data_hoje]
            today_records = sorted(today_records, key=lambda x: int(x['posicao']))
            for r in today_records:
                writer.writerow([
                    r['posicao'],
                    r['clan_nome'],
                    r['fama_atual'],
                    r['pontos_reparo'],
                    r['finalizado'],
                    r['pontos_periodo']
                ])
        print(f"SUCESSO: Criado arquivo legado de debug: {os.path.basename(legacy_filename)}")
    except Exception as e:
        print(f"Aviso: Erro ao criar arquivo legado de debug {legacy_filename}: {e}")
        
    return historico_path

def get_fallback_from_history(historico_path, conta_tipo, data_hoje, dia_batalha):
    """Obtem o ultimo registro valido do historico para a mesma conta como fallback."""
    if not os.path.exists(historico_path):
        return []
    
    try:
        historical_rows = []
        with open(historico_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                historical_rows.append(row)
                
        # Achar a data mais recente antes da data de hoje que contenha essa conta
        dates_before_today = sorted(list(set(
            row['data_coleta'] for row in historical_rows 
            if row['data_coleta'] < data_hoje and row.get('conta_tipo') == conta_tipo
        )), reverse=True)
        
        if dates_before_today:
            latest_date = dates_before_today[0]
            print(f"Fallback: Usando dados de {conta_tipo} da data {latest_date}")
            fallback_records = []
            for row in historical_rows:
                if row['data_coleta'] == latest_date and row.get('conta_tipo') == conta_tipo:
                    new_row = row.copy()
                    new_row['data_coleta'] = data_hoje
                    new_row['dia_batalha'] = dia_batalha
                    fallback_records.append(new_row)
            return fallback_records
    except Exception as e:
        print(f"Aviso: Erro ao buscar fallback no historico: {e}")
        
    return []

def collect_boat_data():
    headers, base_url, clan_tag_pri, clan_tag_sec = get_config()
    
    print("=" * 60)
    print("COLETANDO STATUS BARCOS - AMBAS CONTAS")
    print("=" * 60)
    
    print("\n--- CONTA PRINCIPAL ---")
    collect_boat_data_for_clan(headers, base_url, clan_tag_pri, '_pri')
    
    print("\n--- CONTA SECUNDARIA ---")
    collect_boat_data_for_clan(headers, base_url, clan_tag_sec, '_sec')
    
    print("\n" + "=" * 60)
    print("COLETA DE STATUS BARCOS CONCLUIDA")
    print("=" * 60)

if __name__ == "__main__":
    collect_boat_data()
