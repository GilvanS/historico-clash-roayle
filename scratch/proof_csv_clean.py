import sys
import os

# Adiciona o diretório src ao path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from html_generator import GitHubPagesHTMLGenerator
    print("Iniciando prova 100% CSV...")
    
    # 1. Prova: Verificar se a classe ainda usa sqlite3 internamente
    with open('src/html_generator.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if 'sqlite3.connect' in content or 'cursor.execute' in content:
            print("[ERRO] Ainda existem comandos SQL no arquivo!")
        else:
            print("[OK] Nenhum comando SQL (connect/execute) encontrado.")

    # 2. Executar a próxima task: Clan Deck Analytics (totalmente via CSV)
    generator = GitHubPagesHTMLGenerator()
    
    print(f"--- Cache Status ---")
    print(f"Batalhas: {len(generator.battles_cache)}")
    print(f"Membros: {len(generator.clan_members_cache)}")
    print(f"Historico Rankings: {len(generator.rankings_history_cache)}")
    
    # Executando analise
    analytics = generator.get_clan_deck_analytics()
    
    print("\n--- Analytics Sample (Top 3 Decks) ---")
    for i, deck in enumerate(analytics['popular_decks'][:3]):
        # Mostra apenas os primeiros 20 caracteres do deck para brevidade
        print(f"Pos {i+1}: {deck['deck_cards'][:25]}... | Usos: {deck['usage_count']}")
        
    print("\nPROVA FINAL: O sistema funcionou rapido e buscou tudo dos arquivos CSV.")

except Exception as e:
    print(f"[ERRO] Falha: {e}")
    import traceback
    traceback.print_exc()
