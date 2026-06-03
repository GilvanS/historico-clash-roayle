from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # Capturar todos os erros com stack trace
    all_errors = []
    def on_error(err):
        all_errors.append({
            "message": err.message,
            "stack": err.stack if hasattr(err, 'stack') else 'no stack',
        })
    
    page.on("pageerror", on_error)
    
    print("Navegando...")
    page.goto("https://gilvans.github.io/historico-clash-roayle/", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    
    # Capturar erros do console também
    logs = page.evaluate("""() => {
        return window.__errors || [];
    }""")
    
    print("\n=== PAGE ERRORS ===")
    for e in all_errors:
        print(f"Message: {e['message']}")
        print(f"Stack: {e['stack'][:500]}")
        print("---")
    
    # Tentar compilar cada script individualmente
    print("\n=== TESTE DE COMPILAÇÃO DOS SCRIPTS ===")
    for i in range(7):
        test_result = page.evaluate(f"""(i) => {{
            var scripts = document.querySelectorAll('script');
            if (i >= scripts.length) return 'script not found';
            var code = scripts[i].textContent;
            try {{
                new Function(code);
                return 'OK - ' + code.length + ' chars';
            }} catch(e) {{
                // Encontrar linha do erro
                var lines = code.split('\\n');
                var errorMsg = e.message;
                return 'ERROR: ' + errorMsg + ' | code length: ' + code.length + ' chars | first 200: ' + code.substring(0,200);
            }}
        }}""", i)
        print(f"Script {i}: {test_result[:300]}")
    
    browser.close()
