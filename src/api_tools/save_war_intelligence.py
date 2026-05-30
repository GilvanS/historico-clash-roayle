import os
import requests
import csv
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_account_clans():
    """Lê players.csv e retorna os clãs de todas as contas."""
    accounts = []
    try:
        import sys; sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import config
        players_path = os.path.join(config.DATA_DIR, 'players.csv')
    except:
        players_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'csv', 'players.csv')
    
    if os.path.exists(players_path):
        with open(players_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                player_tag = row.get('player_tag', '')
                clan_tag = row.get('clan_tag', '').replace('#', '')
                clan_name = row.get('clan_name', '')
                
                if clan_tag and clan_tag != '':
                    accounts.append({
                        'player_tag': player_tag,
                        'clan_tag': clan_tag,
                        'clan_name': clan_name
                    })
    
    return accounts


def get_war_decks(player_tag):
    """Busca os 4 decks históricos/recentes de um jogador na guerra."""
    headers, base_url = get_config()
    player_tag_url = player_tag.replace('#', '%23')
    r = requests.get(f"{base_url}/players/{player_tag_url}/battlelog", headers=headers, timeout=15)
    
    decks = []
    if r.status_code == 200:
        battles = r.json()
        for b in battles:
            if b.get('type') in ['clanWarAttack', 'clanWarDuel', 'riverRacePvP']:
                team = b.get('team', [{}])[0]
                cards = sorted([c.get('name') for c in team.get('cards', [])])
                deck_str = ", ".join(cards)
                if deck_str not in decks:
                    decks.append(deck_str)
            if len(decks) >= 4:
                break
    
    return decks


def get_config():
    """Retorna config da API."""
    token = os.getenv('CR_API_TOKEN')
    headers = {'Authorization': f'Bearer {token}'}
    base_url = "https://proxy.royaleapi.dev/v1"
    return headers, base_url


def collect_war_for_clan(clan_tag, clan_name, output_file):
    """Coleta inteligência de guerra para um clã específico."""
    headers, base_url = get_config()
    
    print(f"\n📡 Analisando Clã: {clan_name} ({clan_tag})...")
    
    clan_tag_url = '%23' + clan_tag.replace('#', '')
    r = requests.get(f"{base_url}/clans/{clan_tag_url}/currentriverrace", headers=headers, timeout=15)
    
    if r.status_code != 200:
        print(f"   Erro ao acessar dados da corrida: {r.status_code}")
        return False
    
    all_clans = r.json().get('clans', [])
    
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['Ranking', 'Cla', 'Jogador', 'Lutou_Hoje', 'Ataques_Feitos', 'Fama_Hoje', 'Deck_1', 'Deck_2', 'Deck_3', 'Deck_4'])
        
        for clan_info in all_clans:
            info_clan_name = clan_info.get('name')
            info_clan_tag = clan_info.get('tag')
            info_clan_tag_url = info_clan_tag.replace('#', '%23')
            
            print(f"   📡 Analisando Clã: {info_clan_name}...")
            
            r_clan = requests.get(f"{base_url}/clans/{info_clan_tag_url}/currentriverrace", headers=headers, timeout=15)
            if r_clan.status_code == 200:
                participants = r_clan.json().get('clan', {}).get('participants', [])
                top_5 = sorted(participants, key=lambda x: x.get('fame', 0), reverse=True)[:5]
                
                for i, p in enumerate(top_5):
                    decks_usados_hoje = p.get('decksUsedToday', 0)
                    lutou = "Sim" if decks_usados_hoje > 0 else "Nao"
                    
                    print(f"      👤 {i+1}º: {p.get('name')} (Lutou: {lutou} | Decks: {decks_usados_hoje}/4)")
                    
                    found_decks = get_war_decks(p.get('tag'))
                    
                    while len(found_decks) < 4:
                        found_decks.append("Deck nao encontrado no log recente")
                    
                    writer.writerow([
                        i + 1,
                        info_clan_name,
                        p.get('name'),
                        lutou,
                        f"{decks_usados_hoje}/4",
                        p.get('fame'),
                        found_decks[0],
                        found_decks[1],
                        found_decks[2],
                        found_decks[3]
                    ])
    
    return True


def collect_all_wars():
    """Coleta inteligência de guerra para todas as contas."""
    accounts = get_account_clans()
    
    if not accounts:
        print("Erro: Nenhuma conta encontrada em players.csv")
        return
    
    print(f"\n🚀 Iniciando coleta de Inteligencia de Guerra para {len(accounts)} conta(s)...")
    
    os.makedirs('data/csv', exist_ok=True)
    today = datetime.now().strftime('%Y_%m_%d')
    
    for account in accounts:
        player_tag = account['player_tag']
        clan_tag = account['clan_tag']
        clan_name = account['clan_name']
        
        # Nome do arquivo: inteligencia_guerra_SEC_YYYY_MM_DD.csv para secundaria
        if '2220UQQ0UU' in player_tag:
            output_file = f'data/csv/inteligencia_guerra_sec_{today}.csv'
        else:
            output_file = f'data/csv/inteligencia_guerra_{today}.csv'
        
        print(f"\n{'='*50}")
        print(f"  Conta: {player_tag} | Clã: {clan_name}")
        print(f"{'='*50}")
        
        success = collect_war_for_clan(clan_tag, clan_name, output_file)
        
        if success:
            print(f"\n✅ SUCESSO: {output_file}")


if __name__ == "__main__":
    collect_all_wars()