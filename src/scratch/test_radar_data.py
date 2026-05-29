import os
import sys
import traceback
from dotenv import load_dotenv

# Reconfigura o stdout para usar UTF-8 para evitar erros de caractere no Windows
sys.stdout.reconfigure(encoding='utf-8')

# Adiciona src ao sys.path para podermos importar html_generator
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(src_dir)

# Carrega as variaveis de ambiente
dotenv_path = os.path.join(os.path.dirname(src_dir), '.env')
load_dotenv(dotenv_path)

print(f"Buscando .env em: {dotenv_path}")
print(f"CR_PLAYER_TAG: {os.getenv('CR_PLAYER_TAG')}")
print(f"CR_PLAYER_TAG_SEC: {os.getenv('CR_PLAYER_TAG_SEC')}")

try:
    from html_generator import GitHubPagesHTMLGenerator
    gen = GitHubPagesHTMLGenerator()
    
    print("\n--- Informacoes do Generator ---")
    print(f"Tracked Tags: {gen.tracked_tags}")
    
    # 1. Testar Conta Principal
    print("\n--- Testando Conta Principal (#2QR292P) ---")
    pri_data = gen.get_war_radar_data('#2QR292P')
    print(f"Chaves clans_by_date: {list(pri_data.keys()) if pri_data else 'None'}")
    if pri_data:
        clans_by_date = pri_data.get('clans_by_date', {})
        print(f"Datas de clans_by_date: {list(clans_by_date.keys())}")
        for date, clans in clans_by_date.items():
            print(f"  {date}: {len(clans)} clans")
            if clans:
                clan_0 = clans[0]
                print(f"    Primeiro clan: {clan_0['name']} (is_me: {clan_0['is_me']}, players: {len(clan_0['players'])})")
    
    # 2. Testar Conta Secundaria
    print("\n--- Testando Conta Secundaria (#2220UQQ0UU) ---")
    sec_data = gen.get_war_radar_data('#2220UQQ0UU')
    print(f"Chaves clans_by_date: {list(sec_data.keys()) if sec_data else 'None'}")
    if sec_data:
        clans_by_date = sec_data.get('clans_by_date', {})
        print(f"Datas de clans_by_date: {list(clans_by_date.keys())}")
        for date, clans in clans_by_date.items():
            print(f"  {date}: {len(clans)} clans")
            if clans:
                clan_0 = clans[0]
                print(f"    Primeiro clan: {clan_0['name']} (is_me: {clan_0['is_me']}, players: {len(clan_0['players'])})")
                
except Exception as e:
    print(f"\n[ERRO] Ocorreu uma excecao:")
    traceback.print_exc()
