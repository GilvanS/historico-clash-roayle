import os
import requests
import csv
import json
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Forcar UTF-8 no terminal
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()


# Campos para o CSV de decks de guerra
WAR_FIELDNAMES = [
    'data_coleta', 'nome_jogador', 'tag_cla', 'nome_cla', 
    'fama_atual', 'posicao_no_top', 'categoria_top', 
    'deck_1', 'deck_1_tipo', 'deck_2', 'deck_2_tipo', 'deck_3', 'deck_3_tipo', 'deck_4', 'deck_4_tipo',
    'resultado_dia', 'lutou_hoje'
]

script_dir = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(script_dir)), 'data', 'csv')

def get_clan_tag():
    token = os.getenv('CR_API_TOKEN')
    player_tag = os.getenv('CR_PLAYER_TAG').replace('#', '%23')
    r = requests.get(f"https://proxy.royaleapi.dev/v1/players/{player_tag}", headers={'Authorization': f'Bearer {token}'})
    if r.status_code == 200:
        return r.json().get('clan', {}).get('tag')
    return None

def format_deck(cards):
    if not cards: return ""
    return " | ".join(sorted(c.get('name', '') for c in cards))

def collect_top_decks():
    token = os.getenv('CR_API_TOKEN')
    my_clan_tag = get_clan_tag()
    if not token or not my_clan_tag:
        print("Erro: Credenciais ou Clan Tag nao encontrados.")
        return

    print(f"Buscando dados da guerra para o cla {my_clan_tag}...")
    clan_url = my_clan_tag.replace('#', '%23')
    r = requests.get(f"https://proxy.royaleapi.dev/v1/clans/{clan_url}/currentriverrace", headers={'Authorization': f'Bearer {token}'})
    
    if r.status_code != 200:
        print(f"Erro ao buscar guerra: {r.status_code}")
        return

    race_data = r.json()
    all_participants = []
    my_clan_participants = []
    
    # Coletar participantes
    for clan in race_data.get('clans', []):
        c_tag = clan.get('tag')
        c_name = clan.get('name')
        for p in clan.get('participants', []):
            p['clanTag'] = c_tag
            p['clanName'] = c_name
            all_participants.append(p)
            if c_tag == my_clan_tag:
                my_clan_participants.append(p)

    # Ordenar por fama (descendente)
    all_participants.sort(key=lambda x: x.get('fame', 0), reverse=True)
    my_clan_participants.sort(key=lambda x: x.get('fame', 0), reverse=True)
    
    top_global = all_participants[:10]
    top_clan = my_clan_participants[:10]

    # Unir e remover duplicatas (usando a tag)
    players_to_fetch = []
    seen_tags = set()

    for p in top_clan:
        if p['tag'] not in seen_tags:
            p['categoria'] = 'Top Cla'
            players_to_fetch.append(p)
            seen_tags.add(p['tag'])
            
    for p in top_global:
        if p['tag'] not in seen_tags:
            p['categoria'] = 'Top Global'
            players_to_fetch.append(p)
            seen_tags.add(p['tag'])
        else:
            # Se ja esta no top cla, marcamos como ambos
            for ptf in players_to_fetch:
                if ptf['tag'] == p['tag']:
                    ptf['categoria'] = 'Top Cla/Global'

    print(f"Identificados {len(players_to_fetch)} jogadores de elite. Coletando decks (Guerra + Barco)...")
    
    results = []
    data_hoje = (datetime.now() - timedelta(hours=3)).strftime('%Y-%m-%d')

    for i, p in enumerate(players_to_fetch, 1):
        p_tag = p.get('tag')
        p_name = p.get('name')
        print(f"  [{i}] {p_name} ({p_tag}) - Fama: {p.get('fame')} [{p['categoria']}]")
        
        # Buscar battle log do jogador
        p_tag_url = p_tag.replace('#', '%23')
        br = requests.get(f"https://proxy.royaleapi.dev/v1/players/{p_tag_url}/battlelog", headers={'Authorization': f'Bearer {token}'})

        decks = []
        deck_types = []
        wins = 0
        losses = 0
        lutou = "Nao"
        
        if br.status_code == 200:
            battles = br.json()
            for b in battles:
                battle_type = b.get('type', '')
                # Inclui todos os tipos de guerra
                if battle_type in ['clanWarWarDay', 'boatBattle', 'riverRacePvP', 'riverRaceDuel']:
                    lutou = "Sim"
                    team = b.get('team', [{}])[0]
                    deck_str = format_deck(team.get('cards', []))
                    if deck_str and deck_str not in decks:
                        decks.append(deck_str)
                        # Mapeia tipo de batalha para label
                        type_label = {
                            'clanWarWarDay': 'Guerra',
                            'boatBattle': 'Barco',
                            'riverRacePvP': 'Range Battle',
                            'riverRaceDuel': 'Duelo'
                        }.get(battle_type, battle_type)
                        deck_types.append(type_label)
                    
                    p_crowns = team.get('crowns', 0)
                    opp_crowns = b.get('opponent', [{}])[0].get('crowns', 0)
                    if p_crowns > opp_crowns: wins += 1
                    else: losses += 1
                    
                    if len(decks) >= 4: break
        
        while len(decks) < 4:
            decks.append("N/A")
            deck_types.append("N/A")
        
        results.append({
            'data_coleta': data_hoje,
            'nome_jogador': p_name,
            'tag_cla': p.get('clanTag'),
            'nome_cla': p.get('clanName'),
            'fama_atual': p.get('fame'),
            'posicao_no_top': i,
            'categoria_top': p['categoria'],
            'deck_1': decks[0],
            'deck_1_tipo': deck_types[0] if len(deck_types) > 0 else 'N/A',
            'deck_2': decks[1],
            'deck_2_tipo': deck_types[1] if len(deck_types) > 1 else 'N/A',
            'deck_3': decks[2],
            'deck_3_tipo': deck_types[2] if len(deck_types) > 2 else 'N/A',
            'deck_4': decks[3],
            'deck_4_tipo': deck_types[3] if len(deck_types) > 3 else 'N/A',
            'resultado_dia': f"{wins}V {losses}D" if lutou == "Sim" else "N/A",
            'lutou_hoje': lutou
        })


    # Salvar no CSV com inteligência de merge
    file_path = os.path.join(DATA_DIR, 'war_decks_top_players.csv')
    existing_data = []
    
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                existing_data = list(reader)
        except Exception as e:
            print(f"Erro ao ler CSV existente: {e}")

    # Indexar dados existentes por (data, nome)
    data_map = {}
    for row in existing_data:
        # Normalize date format from DD/MM/YYYY to YYYY-MM-DD on the fly
        dt_str = row['data_coleta']
        if '/' in dt_str:
            try:
                dt_str = datetime.strptime(dt_str, '%d/%m/%Y').strftime('%Y-%m-%d')
                row['data_coleta'] = dt_str
            except ValueError:
                pass
        key = (row['data_coleta'], row.get('nome_jogador', ''))
        data_map[key] = row

    # Merge novos resultados
    for new_row in results:
        key = (new_row['data_coleta'], new_row['nome_jogador'])
        if key in data_map:
            old_row = data_map[key]
            # Critério de atualização: Se o novo tem mais decks preenchidos ou se o antigo era "Nao" e o novo é "Sim"
            old_decks_count = sum(1 for i in range(1, 5) if old_row.get(f'deck_{i}') and old_row.get(f'deck_{i}') != "N/A")
            new_decks_count = sum(1 for i in range(1, 5) if new_row.get(f'deck_{i}') and new_row.get(f'deck_{i}') != "N/A")
            
            if new_decks_count >= old_decks_count or (old_row['lutou_hoje'] == "Nao" and new_row['lutou_hoje'] == "Sim"):
                data_map[key] = new_row
        else:
            data_map[key] = new_row

    # Converter de volta para lista e ordenar por data (desc) e posicao
    final_results = list(data_map.values())
    final_results.sort(key=lambda x: (datetime.strptime(x['data_coleta'], '%Y-%m-%d'), -int(x['posicao_no_top'])), reverse=True)

    with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=WAR_FIELDNAMES, delimiter=';')
        writer.writeheader()
        # Filtrar campos para garantir compatibilidade com WAR_FIELDNAMES
        cleaned_results = [{k: r[k] for k in WAR_FIELDNAMES if k in r} for r in final_results]
        writer.writerows(cleaned_results)

    print(f"\nSucesso! Decks atualizados em {file_path}")
    
    # Trigger HTML Generation
    try:
        print("Atualizando Dashboard HTML...")
        from html_generator import GitHubPagesHTMLGenerator
        gen = GitHubPagesHTMLGenerator()
        html_content = gen.generate_html_report()
        # Salvar o arquivo no diretório raiz
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(root_dir, 'index.html')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Dashboard atualizado com sucesso em {index_path}!")

    except Exception as e:
        print(f"Erro ao atualizar HTML: {e}")

if __name__ == "__main__":
    collect_top_decks()
