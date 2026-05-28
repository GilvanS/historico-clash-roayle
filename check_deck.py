import csv

path = 'src/data_clan/guerra_historico.csv'
with open(path, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f, delimiter=';')
    rows = list(reader)

# Ver registros de hoje para #2QR292P
hoje = [r for r in rows if r.get('conta_tipo', '') == '#2QR292P' and r.get('data_coleta', '') == '2026-05-28']
print(f'Registros de #2QR292P para hoje: {len(hoje)}')
for r in hoje:
    nome = r.get('player_nome', '')[:20].encode('ascii', 'replace').decode()
    fame = r.get('player_fame', '')
    clan = r.get('clan_nome', '')[:20].encode('ascii', 'replace').decode()
    clan_tag = r.get('clan_tag', '')
    decks = r.get('decks_usados', '')
    war_b = r.get('war_battles_count', '')
    has_deck = 'SIM' if r.get('deck_1', '').strip() else 'NAO'
    print(f"  {nome:20} | clan={clan:20} | clan_tag={clan_tag} | fame={fame} | decks={decks} | war_b={war_b} | deck={has_deck}")

print()
# Ver se clan_nome eh vazio ou nao
sem_clan = [r for r in hoje if not r.get('clan_nome', '').strip()]
com_clan = [r for r in hoje if r.get('clan_nome', '').strip()]
print(f'Com clan_nome: {len(com_clan)} | Sem clan_nome: {len(sem_clan)}')
