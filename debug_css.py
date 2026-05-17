from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto('file:///A:/Workspace/historico-clash-roayle/index.html')
    page.wait_for_load_state('networkidle')
    
    # Check for radar CSS selectors in stylesheets
    all_css = page.evaluate("() => { const sheets = document.styleSheets; let result = []; for(let s of sheets) { try { for(let r of s.cssRules) { if(r.selectorText && (r.selectorText.includes('rd-') || r.selectorText.includes('radar'))) result.push(r.selectorText); } } catch(e){} } return result; }")
    print(f"Total radar CSS selectors: {len(all_css)}")
    for c in all_css[:5]:
        try:
            print(f"  - {c}")
        except:
            pass
    
    # Get computed styles for specific elements
    player_deck = page.evaluate("() => { const el = document.querySelector('.rd-deck'); if(!el) return 'NOT FOUND'; const style = window.getComputedStyle(el); return `display:${style.display}, width:${style.width}`; }")
    print(f"rd-deck computed: {player_deck}")
    
    # Count style tags
    style_count = page.evaluate("() => document.querySelectorAll('style').length")
    print(f"Total style tags: {style_count}")
    
    # Get all stylesheets text length
    css_total = page.evaluate("() => { let total = 0; const sheets = document.styleSheets; for(let s of sheets) { try { total += s.cssRules.length; } catch(e){} } return total; }")
    print(f"Total CSS rules: {css_total}")
    
    browser.close()