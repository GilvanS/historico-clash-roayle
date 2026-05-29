from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto('file:///A:/Workspace/historico-clash-roayle/index.html')
    page.wait_for_load_state('networkidle')
    
    # Get all style tag contents
    styles = page.evaluate("() => { return Array.from(document.querySelectorAll('style')).map((s, i) => `Style ${i}: ${s.textContent.substring(0, 300)}...`); }")
    for s in styles:
        print(s[:300])
        print("---")
    
    # Check if rd-section text exists in any style
    has_rd_section = page.evaluate("() => document.querySelector('style') ? document.querySelector('style').textContent.includes('rd-section') : false")
    print(f"Has rd-section in styles: {has_rd_section}")
    
    # Check inline style tag content length
    style_lengths = page.evaluate("() => Array.from(document.querySelectorAll('style')).map(s => s.textContent.length)")
    print(f"Style content lengths: {style_lengths}")
    
    # Check specifically the 4th style tag (war-intel section)
    fourth_style = page.evaluate("() => { const styles = document.querySelectorAll('style'); return styles.length >= 4 ? styles[3].textContent.substring(0, 200) : 'NOT ENOUGH STYLES'; }")
    print(f"4th style content: {fourth_style}")
    
    browser.close()