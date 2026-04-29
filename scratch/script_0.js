
        function updateBattlePreview(deckId, battleIdx, battleDataJson) {
            try {
                const data = JSON.parse(decodeURIComponent(battleDataJson));
                const previewContainer = document.getElementById('preview-' + deckId);
                if (!previewContainer) return;
                
                const myDeckHtml = getMiniGridJS(data.my_deck, 'my-deck-side');
                const oppDeckHtml = getMiniGridJS(data.opp_deck, 'opp-deck-side');
                
                previewContainer.innerHTML = `
                    <div style="text-align:center;"><small style="font-size:0.5em;color:#718096;font-weight:bold;">MEU DECK</small>${myDeckHtml}</div>
                    <div style="font-weight:bold;color:#cbd5e0;font-size:0.8em;">VS</div>
                    <div style="text-align:center;"><small style="font-size:0.5em;color:#718096;font-weight:bold;">OPONENTE</small>${oppDeckHtml}</div>
                `;
                
                const timeline = document.querySelector('.timeline-' + deckId);
                if (timeline) {
                    timeline.querySelectorAll('.cr-battle-badge').forEach((b, i) => {
                        if (i === battleIdx) {
                            b.style.boxShadow = '0 0 0 3px #4299e1';
                            b.style.transform = 'scale(1.1)';
                        } else {
                            b.style.boxShadow = 'none';
                            b.style.transform = 'scale(1)';
                        }
                    });
                }
            } catch(e) { console.error("Error updating preview:", e); }
        }
        
        function getMiniGridJS(deckStr, sideClass) {
            if (!deckStr) return '<div style="width:100px;height:60px;border:1px dashed #ccc;display:flex;align-items:center;justify-content:center;font-size:0.7em;color:#999;">N/D</div>';
            const cards = deckStr.replace(/ \| /g, '|').split('|');
            return `
                <div class="${sideClass}">
                    <div class="cr-cards-grid" style="gap:2px;padding:0;">
                        <div class="cr-cards-row" style="gap:2px;">${cards.slice(0,4).map(c => `<div class="cr-card-wrap" style="width:22px;height:26px;" title="${c.trim()}"><img src="cards/${c.trim().toLowerCase().replace(/\s+/g, '-').replace(/\./g, '')}.png" class="cr-card-img" onerror="this.src='https://royaleapi.github.io/cr-api-assets/cards/${c.trim().toLowerCase().replace(/\s+/g, '-').replace(/\./g, '')}.png';"></div>`).join('')}</div>
                        <div class="cr-cards-row" style="gap:2px;">${cards.slice(4,8).map(c => `<div class="cr-card-wrap" style="width:22px;height:26px;" title="${c.trim()}"><img src="cards/${c.trim().toLowerCase().replace(/\s+/g, '-').replace(/\./g, '')}.png" class="cr-card-img" onerror="this.src='https://royaleapi.github.io/cr-api-assets/cards/${c.trim().toLowerCase().replace(/\s+/g, '-').replace(/\./g, '')}.png';"></div>`).join('')}</div>
                    </div>
                </div>
            `;
        }

        function switchDeckTab(event, tabName) {
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
            document.getElementById('tab-' + tabName).classList.add('active');
            if (event) event.currentTarget.classList.add('active');
        }
        