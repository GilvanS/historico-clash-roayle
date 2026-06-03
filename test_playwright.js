const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  // Capturar erros JS
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push('CONSOLE: ' + msg.text());
  });
  
  console.log('Navegando para GitHub Pages...');
  await page.goto('https://gilvans.github.io/historico-clash-roayle/', { 
    waitUntil: 'networkidle',
    timeout: 60000 
  });
  
  console.log('Aguardando 5s para scripts executarem...');
  await page.waitForTimeout(5000);
  
  // Verificar se a função existe
  const result = await page.evaluate(() => {
    return {
      func1: typeof window['filterDecks_acc_2QR292P'],
      func2: typeof window['filterDecks_acc_2220UQQ0UU'],
      grid1: document.getElementById('acc-2QR292P-deckGrid') ? 'found' : 'NOT FOUND',
      grid2: document.getElementById('acc-2220UQQ0UU-deckGrid') ? 'found' : 'NOT FOUND',
      cards1: document.getElementById('acc-2QR292P-deckGrid')?.querySelectorAll('.cr-deck-card').length,
      cards2: document.getElementById('acc-2220UQQ0UU-deckGrid')?.querySelectorAll('.cr-deck-card').length,
      hidden1: document.getElementById('acc-2QR292P-deckGrid')?.querySelectorAll('.cr-deck-card[style*="none"]').length,
      hidden2: document.getElementById('acc-2220UQQ0UU-deckGrid')?.querySelectorAll('.cr-deck-card[style*="none"]').length,
    };
  });
  
  console.log('\n=== RESULTADO ===');
  console.log(JSON.stringify(result, null, 2));
  
  if (errors.length > 0) {
    console.log('\n=== ERROS JS ===');
    errors.forEach(e => console.log('  -', e));
  }
  
  // Testar filtro: mudar para 5 decks na conta primária
  if (result.func1 === 'function') {
    console.log('\n=== TESTE FILTRO: 5 decks ===');
    await page.evaluate(() => {
      const sel = document.getElementById('acc-2QR292P-deckFilter');
      sel.value = '5';
      sel.onchange(sel.value);
    });
    await page.waitForTimeout(500);
    
    const after5 = await page.evaluate(() => {
      return {
        hidden: document.getElementById('acc-2QR292P-deckGrid')?.querySelectorAll('.cr-deck-card[style*="none"]').length,
        total: document.getElementById('acc-2QR292P-deckGrid')?.querySelectorAll('.cr-deck-card').length,
      };
    });
    console.log('Após selecionar 5:', JSON.stringify(after5));
  }
  
  await browser.close();
})();
