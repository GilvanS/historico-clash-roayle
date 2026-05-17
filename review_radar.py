from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    
    # Desktop viewport
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto('file:///A:/Workspace/historico-clash-roayle/index.html')
    page.wait_for_load_state('networkidle')
    
    radar = page.locator('.rd-section')
    if radar.count() > 0:
        radar.scroll_into_view_if_needed()
        page.wait_for_timeout(1000)
    
    # Full page screenshot
    page.screenshot(path='A:/Workspace/historico-clash-roayle/radar_desktop.png', full_page=False)
    print("Desktop screenshot saved")
    
    # Mobile viewport
    page.set_viewport_size({"width": 375, "height": 667})
    page.wait_for_timeout(500)
    radar.scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    page.screenshot(path='A:/Workspace/historico-clash-roayle/radar_mobile.png', full_page=False)
    print("Mobile screenshot saved")
    
    # Get detailed DOM info
    rd_section = page.locator('.rd-section')
    if rd_section.count() > 0:
        bounding = rd_section.first.bounding_box()
        print(f"Radar bounding box: {bounding}")
        
        # Check each clan card
        clan_cards = page.locator('.rd-clan').all()
        for i, card in enumerate(clan_cards):
            card_box = card.bounding_box()
            players = card.locator('.rd-player').count()
            decks = card.locator('.rd-deck').count()
            imgs = card.locator('.rd-deck img').count()
            print(f"Clan {i+1}: box={card_box}, players={players}, decks={decks}, imgs={imgs}")
    
    browser.close()