from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    all_errors = []
    page.on("pageerror", lambda err: all_errors.append(err.message))
    
    print("Navegando para arquivo local...")
    page.goto("file:///A:/Workspace/historico-clash-roayle/docs/index.html", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(5000)
    
    result = page.evaluate("""() => {
        var g1 = document.getElementById('acc-2QR292P-deckGrid');
        var g2 = document.getElementById('acc-2220UQQ0UU-deckGrid');
        return {
            func1: typeof window['filterDecks_acc_2QR292P'],
            func2: typeof window['filterDecks_acc_2220UQQ0UU'],
            cards1: g1 ? g1.querySelectorAll('.cr-deck-card').length : 'N/A',
            cards2: g2 ? g2.querySelectorAll('.cr-deck-card').length : 'N/A',
            hidden1: g1 ? g1.querySelectorAll('.cr-deck-card[style*="none"]').length : 'N/A',
            hidden2: g2 ? g2.querySelectorAll('.cr-deck-card[style*="none"]').length : 'N/A',
        }
    }""")
    
    print("\n=== RESULTADO ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
    
    if all_errors:
        print("\n=== ERROS JS ===")
        for e in all_errors:
            print(f"  - {e}")
    else:
        print("\n=== SEM ERROS JS ===")
    
    # Testar filtro
    if result.get('func1') == 'function':
        print("\n=== TESTE FILTRO ===")
        
        # 5 decks
        page.evaluate("""() => {
            var sel = document.getElementById('acc-2QR292P-deckFilter');
            sel.value = '5';
            sel.onchange(sel.value);
        }""")
        page.wait_for_timeout(500)
        r5 = page.evaluate("""() => {
            var g = document.getElementById('acc-2QR292P-deckGrid');
            return {hidden: g.querySelectorAll('.cr-deck-card[style*="none"]').length, total: g.querySelectorAll('.cr-deck-card').length};
        }""")
        print(f"  5 Decks: {r5}")
        
        # 10 decks
        page.evaluate("""() => {
            var sel = document.getElementById('acc-2QR292P-deckFilter');
            sel.value = '10';
            sel.onchange(sel.value);
        }""")
        page.wait_for_timeout(500)
        r10 = page.evaluate("""() => {
            var g = document.getElementById('acc-2QR292P-deckGrid');
            return {hidden: g.querySelectorAll('.cr-deck-card[style*="none"]').length, total: g.querySelectorAll('.cr-deck-card').length};
        }""")
        print(f"  10 Decks: {r10}")
        
        # Todos
        page.evaluate("""() => {
            var sel = document.getElementById('acc-2QR292P-deckFilter');
            sel.value = '999';
            sel.onchange(sel.value);
        }""")
        page.wait_for_timeout(500)
        rAll = page.evaluate("""() => {
            var g = document.getElementById('acc-2QR292P-deckGrid');
            return {hidden: g.querySelectorAll('.cr-deck-card[style*="none"]').length, total: g.querySelectorAll('.cr-deck-card').length};
        }""")
        print(f"  Todos: {rAll}")
    else:
        print("\n=== FUNCAO NAO EXISTE ===")
    
    browser.close()
