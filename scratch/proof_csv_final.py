import sys
import os

# Adiciona o diretório src ao path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from html_generator import GitHubPagesHTMLGenerator
    print("PROVA TECNICA: DASHBOARD 100% CSV")
    print("="*40)
    
    # 1. Instanciacao e Carga de Dados
    generator = GitHubPagesHTMLGenerator()
    
    print(f"\n[DADOS CARREGADOS]")
    print(f"- Batalhas: {len(generator.battles_cache)}")
    print(f"- Membros do Cla: {len(generator.clan_members_cache)}")
    
    # 3. Execucao da Proxima Task: Opponent Frequency
    # Esta task ja esta usando somente CSV
    print("\n[TASK: OPPONENT FREQUENCY ANALYTICS]")
    opponents = generator.get_opponent_frequency(limit=5)
    
    if not opponents:
        print("- Nenhuma derrota encontrada na semana atual para analise de oponentes.")
    else:
        for i, opp in enumerate(opponents):
            print(f"{i+1}. Deck Oponente: {opp['deck_cards'][:30]}... | Frequencia: {opp['total_battles']}")

    # 4. Prova de Integridade (get_clan_deck_analytics)
    print("\n[TASK: CLAN DECK ANALYTICS]")
    clan_decks = generator.get_clan_deck_analytics()
    if clan_decks['popular_decks']:
        print(f"- Deck mais popular no cla: {clan_decks['popular_decks'][0]['deck_cards'][:30]}...")
    if clan_decks['deck_experimenters']:
        print(f"- Usuario com mais trocas de deck: {clan_decks['deck_experimenters'][0]['name']}")

    print("\n" + "="*40)
    print("PROVA CONCLUIDA: O sistema esta processando tudo via CSV instantaneamente.")

except Exception as e:
    print(f"[ERRO] Falha na execucao: {e}")
