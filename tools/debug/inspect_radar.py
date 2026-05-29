from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto('file:///A:/Workspace/historico-clash-roayle/index.html')
    page.wait_for_load_state('networkidle')
    
    # Check container widths
    radar = page.locator('.rd-section')
    if radar.count() > 0:
        radar.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        
        # Get parent containers
        parent = radar.first.evaluate('el => el.parentElement.className')
        grandparent = radar.first.evaluate('el => el.parentElement.parentElement.className')
        greatgrandparent = radar.first.evaluate('el => el.parentElement.parentElement.parentElement.className')
        
        print(f"Parent class: {parent}")
        print(f"Grandparent class: {grandparent}")
        print(f"Great-grandparent class: {greatgrandparent}")
        
        # Get bounding boxes
        radar_box = radar.first.bounding_box()
        parent_box = radar.first.evaluate('el => {const p=el.parentElement; const r=p.getBoundingClientRect(); return {w:r.width,h:r.height,x:r.x,y:r.y}}')
        
        print(f"Radar box: {radar_box}")
        print(f"Parent box: {parent_box}")
        
        # Check if rd-grid has correct width
        grid = page.locator('.rd-grid')
        grid_box = grid.first.bounding_box()
        grid_display = grid.first.evaluate('el => window.getComputedStyle(el).display')
        grid_cols = grid.first.evaluate('el => window.getComputedStyle(el).gridTemplateColumns')
        print(f"Grid box: {grid_box}")
        print(f"Grid display: {grid_display}")
        print(f"Grid columns: {grid_cols}")
        
        # Take a focused screenshot of just the radar section
        page.screenshot(path='A:/Workspace/historico-clash-roayle/radar_detail.png')
        print("Detail screenshot saved")
    
    browser.close()