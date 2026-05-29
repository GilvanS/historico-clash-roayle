import sys
import os
import json

# Forçar encoding UTF-8 no terminal Windows para evitar UnicodeEncodeError
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Adicionar src ao path para importar corretamente
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from html_generator import GitHubPagesHTMLGenerator
    print("--- INICIANDO DIAGNÓSTICO DE BACKEND ---")
    
    generator = GitHubPagesHTMLGenerator()
    
    print(f"Tags Monitoradas: {generator.tracked_tags}")
    
    for tag in generator.tracked_tags:
        print(f"\nVerificando Tag: {tag}")
        stats = generator.get_player_stats(tag)
        
        if stats:
            print(f"  [OK] Stats encontradas para: {stats.get('name', 'N/A')}")
            battles = generator.get_recent_battles(5, player_tag=tag)
            print(f"  [OK] Batalhas recentes encontradas: {len(battles)}")
        else:
            print(f"  [ERRO] Stats NÃO encontradas para a tag {tag}")
            # Investigar o porquê
            player_csv_path = os.path.join(generator.data_csv_dir, 'players.csv')
            print(f"  [INFO] Verificando arquivo players.csv em: {player_csv_path}")
            if os.path.exists(player_csv_path):
                with open(player_csv_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if tag in content:
                        print(f"  [INFO] A tag EXISTE no players.csv")
                    else:
                        print(f"  [AVISO] A tag NÃO FOI ENCONTRADA no players.csv")
            else:
                print(f"  [ERRO] Arquivo players.csv não encontrado!")

    # Testar a geração das abas especificamente
    html = generator.generate_html_report()
    print("\n--- VALIDAÇÃO DE HTML GERADO ---")
    if "CONTA SECUNDÁRIA" in html:
        print("  [SUCESSO] A string 'CONTA SECUNDÁRIA' está presente no HTML.")
    else:
        print("  [FALHA] A string 'CONTA SECUNDÁRIA' está AUSENTE no HTML.")
        
    if "account-tab-" in html:
        tabs_count = html.count('class="cr-tab')
        content_count = html.count('class="cr-tab-content')
        print(f"  [INFO] Total de abas de conta no HTML: {tabs_count}")
        print(f"  [INFO] Total de containers de conteúdo no HTML: {content_count}")

except Exception as e:
    print(f"\n[ERRO CRÍTICO NO BACKEND]: {str(e)}")
    import traceback
    traceback.print_exc()
