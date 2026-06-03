from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    errors = []
    page.on("pageerror", lambda err: errors.append(err.message))
    page.on("console", lambda msg: errors.append(f"CONSOLE: {msg.text}") if msg.type == "error" else None)
    
    print("Navegando para GitHub Pages...")
    page.goto("https://gilvans.github.io/historico-clash-roayle/", wait_until="networkidle", timeout=60000)
    
    print("Aguardando 5s para scripts executarem...")
    page.wait_for_timeout(5000)
    
    result = page.evaluate("""() => {
        return {
            func1: typeof window['filterDecks_acc_2QR292P'],
            func2: typeof window['filterDecks_acc_2220UQQ0UU'],
            grid1: document.getElementById('acc-2QR292P-deckGrid') ? 'found' : 'NOT FOUND',
            grid2: document.getElementById('acc-2220UQQ0UU-deckGrid') ? 'found' : 'NOT FOUND',
            cards1: document.getElementById('acc-2QR292P-deckGrid')?.querySelectorAll('.cr-deck-card').length,
            cards2: document.getElementById('acc-2220UQQ0UU-deckGrid')?.querySelectorAll('.cr-deck-card').length,
            hidden1: document.getElementById('acc-2QR292P-deckGrid')?.querySelectorAll('.cr-deck-card[style*=\\"none\\"]')?.length,
            hidden2: document.getElementById('acc-2220UQQ0UU-deckGrid')?.querySelectorAll('.cr-deck-card[style*=\\"none\\"]')?.length,
        }
    }""")
    
    print("\n=== RESULTADO ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
    
    if errors:
        print("\n=== ERROS JS ===")
        for e in errors:
            print(f"  - {e}")
    
    # Testar filtro
    if result.get('func1') == 'function':
        print("\n=== TESTE FILTRO: 5 decks ===")
        page.evaluate("""() => {
            const sel = document.getElementById('acc-2QR292P-deckFilter');
            sel.value = '5';
            sel.onchange(sel.value);
        }""")
        page.wait_for_timeout(500)
        
        after5 = page.evaluate("""() => {
            return {
                hidden: document.getElementById('acc-2QR292P-deckGrid')?.querySelectorAll('.cr-deck-card[style*=\\"none\\"]')?.length,
                total: document.getElementById('acc-2QR292P-deckGrid')?.querySelectorAll('.cr-deck-card').length,
            }
        }""")
        print(f"  Apos selecionar 5: {after5}")
    
    browser.close()
