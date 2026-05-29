import sys
import os

fpath = r'a:\Workspace\historico-clash-roayle\src\html_generator.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

target = """                                tipo_icon = {
                                    'Guerra': '⚔️',
                                    'Barco': '🚣',
                                    'Range Battle': '🎯',
                                    'Duelo': '⚡'
                                }.get(deck_tipo, '🛡️')
                                deck_label = f'<div class="rd-deck-label">{tipo_icon} Deck {d} ({deck_tipo})</div>'
                                deck_rows_html += f'<div class="rd-deck-row">{deck_label}<div class="rd-deck">{cards_imgs}</div></div>'"""

replacement = """                                tipo_icon = {
                                    'Guerra': '⚔️',
                                    'Barco': '🚣',
                                    'Range Battle': '🎯',
                                    'Duelo': '⚡'
                                }.get(deck_tipo, '🛡️')
                                
                                copy_link = self.get_copy_deck_link(cards)
                                btn_html = f'<button type="button" onclick="copyDeckLink(event, this, \\'{copy_link}\\')" class="cr-copy-btn-v2" style="border: none; padding: 2px 6px; cursor: pointer; background: transparent; margin-left: 8px;" title="Copiar/Compartilhar"><img src="https://media.ffycdn.net/eu/supercell/jsmnnT9Z8mF79QiwDcsW.png?width=2400" alt="Copiar Deck" style="height: 18px; vertical-align: middle;"></button>'
                                
                                deck_label = f'<div class="rd-deck-label" style="display: flex; align-items: center; justify-content: space-between; width: 100%;">{tipo_icon} Deck {d} ({deck_tipo}){btn_html}</div>'
                                deck_rows_html += f'<div class="rd-deck-row">{deck_label}<div class="rd-deck">{cards_imgs}</div></div>'"""

if target in content:
    content = content.replace(target, replacement)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched successfully!")
else:
    print("Target not found!")
