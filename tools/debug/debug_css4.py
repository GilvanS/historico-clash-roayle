from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto('file:///A:/Workspace/historico-clash-roayle/index.html')
    page.wait_for_load_state('networkidle')
    
    # Check the end of Style 0 (main CSS) to see if our radar CSS is there
    style0_end = page.evaluate("() => { const s = document.querySelectorAll('style')[0]; return s ? s.textContent.substring(s.textContent.length - 2000) : 'NOT FOUND'; }")
    
    # Save to file to avoid encoding issues
    with open('style0_end.txt', 'w', encoding='utf-8') as f:
        f.write(style0_end)
    print(f"Style 0 end saved, length: {len(style0_end)}")
    
    # Also check if rd-grid text exists
    has_rd_grid = page.evaluate("() => { const s = document.querySelectorAll('style')[0]; return s ? s.textContent.includes('rd-grid') : false; }")
    print(f"Style 0 has rd-grid: {has_rd_grid}")
    
    # Check position of "WAR RADAR" in Style 0
    wr_pos = page.evaluate("() => { const s = document.querySelectorAll('style')[0]; return s ? s.textContent.indexOf('WAR RADAR') : -1; }")
    print(f"WAR RADAR position in Style 0: {wr_pos}")
    
    # Check what the last 500 chars of Style 0 say
    last_chars = page.evaluate("() => { const s = document.querySelectorAll('style')[0]; return s ? s.textContent.slice(-500) : 'NOT FOUND'; }")
    with open('style0_last.txt', 'w', encoding='utf-8') as f:
        f.write(last_chars)
    print("Last 500 chars saved to style0_last.txt")
    
    browser.close()