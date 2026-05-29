from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto('file:///A:/Workspace/historico-clash-roayle/index.html')
    page.wait_for_load_state('networkidle')
    
    # Check actual computed styles
    grid = page.locator('.rd-grid').first
    computed_display = page.evaluate("() => window.getComputedStyle(document.querySelector('.rd-grid')).display")
    computed_cols = page.evaluate("() => window.getComputedStyle(document.querySelector('.rd-grid')).gridTemplateColumns")
    
    print(f"rd-grid computed display: {computed_display}")
    print(f"rd-grid computed columns: {computed_cols}")
    
    # Check if our CSS actually has the right selector
    css_text = page.evaluate("() => { const sheets = document.styleSheets; for(let s of sheets) { try { const rules = s.cssRules; for(let r of rules) { if(r.selectorText && r.selectorText.includes('rd-grid')) return r.cssText; } } catch(e){} } return 'NOT FOUND'; }")
    print(f"rd-grid CSS rule: {css_text[:200] if css_text else 'NOT FOUND'}")
    
    # Find our radar styles in computed CSS
    radar_style = page.evaluate("() => { const sheets = document.styleSheets; let found = []; for(let s of sheets) { try { const rules = s.cssRules; for(let r of rules) { if(r.selectorText && r.selectorText.includes('rd-')) found.push(r.selectorText); } } catch(e){} } return found.slice(0,20).join(', '); }")
    print(f"Radar selectors found: {radar_style}")
    
    browser.close()