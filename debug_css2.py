from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto('file:///A:/Workspace/historico-clash-roayle/index.html')
    page.wait_for_load_state('networkidle')
    
    # Check all CSS selectors
    all_css = page.evaluate("() => { const sheets = document.styleSheets; let result = []; for(let s of sheets) { try { for(let r of s.cssRules) { if(r.selectorText) result.push(r.selectorText); } } catch(e){} } return result; }")
    
    # Filter for radar related
    radar_css = [c for c in all_css if 'rd-' in c.lower() or 'radar' in c.lower() or 'war-' in c.lower()]
    print(f"Total rules: {len(all_css)}, Radar rules: {len(radar_css)}")
    
    # Print all unique selectors containing rd
    rd_selectors = sorted(set([c for c in all_css if '.rd' in c]))
    print(f"rd selectors ({len(rd_selectors)}):")
    for c in rd_selectors:
        print(f"  {c}")
    
    # Check style tag sources
    sources = page.evaluate("() => { return Array.from(document.querySelectorAll('style')).map(s => s.parentElement.tagName + ': ' + (s.href || 'inline')); }")
    for s in sources:
        print(f"Style source: {s}")
    
    browser.close()