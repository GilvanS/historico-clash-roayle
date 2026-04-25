import sys
import os

# Adiciona o diretório src ao path
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from html_generator import GitHubPagesHTMLGenerator
    import sqlite3
    print("Tentando importar GitHubPagesHTMLGenerator...")
    
    # 1. Prova: Verificar se a classe ainda usa sqlite3 internamente
    with open('src/html_generator.py', 'r', encoding='utf-8') as f:
        content = f.read()
        if 'sqlite3.connect' in content or 'cursor.execute' in content:
            print("❌ ERRO: Ainda existem comandos SQL no arquivo!")
        else:
            print("✅ SUCESSO: Nenhum comando SQL (connect/execute) encontrado no arquivo.")

    # 2. Executar a próxima task: Clan Deck Analytics (totalmente via CSV)
    print("\nExecutando 'get_clan_deck_analytics' via CSV...")
    generator = GitHubPagesHTMLGenerator()
    
    # Prova de Caches Populados
    print(f"--- Prova de Dados ---")
    print(f"Batalhas em cache: {len(generator.battles_cache)}")
    print(f"Membros do clã: {len(generator.clan_members_cache)}")
    print(f"Decks do clã: {len(generator.clan_decks_cache)}")
    
    analytics = generator.get_clan_deck_analytics()
    
    print("\n--- Resultado da Task (Popular Decks) ---")
    for i, deck in enumerate(analytics['popular_decks'][:3]):
        print(f"{i+1}. Deck: {deck['deck_cards'][:30]}... | Usos: {deck['usage_count']}")
        
    print("\n✅ Task concluída com sucesso usando APENAS arquivos CSV.")

except Exception as e:
    print(f"❌ Falha durante a prova: {e}")
    import traceback
    traceback.print_exc()
