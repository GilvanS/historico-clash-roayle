import csv
with open(r'A:\Workspace\historico-clash-roayle\src\data_clan\inteligencia_guerra_2026_05_16.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f, delimiter=';')
    clans = {}
    for row in reader:
        cla = row.get('Cla', 'Unknown')
        if cla not in clans:
            clans[cla] = {'count': 0, 'with_decks': 0, 'players': []}
        clans[cla]['count'] += 1
        clans[cla]['players'].append(row.get('Jogador', ''))
        deck1 = row.get('Deck_1', '')
        if deck1 and deck1 != 'Deck nao encontrado no log recente':
            clans[cla]['with_decks'] += 1
    
    print(f'Total de clans: {len(clans)}')
    for cla, info in clans.items():
        print(f'  {cla}: {info["count"]} players, {info["with_decks"]} com deck_1')
        print(f'    Players: {info["players"][:3]}')