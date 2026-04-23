#!/usr/bin/env python3
import os

TARGET_FILE = r'a:/Workspace/historico-clash-roayle/src/html_generator.py'

NEW_METHOD = r'''    def generate_repeated_opponents_html(self, opponents):
        """Gera HTML para oponentes repetidos no estilo Premium do CR Dashboard."""
        if not opponents:
            return '<p>Nenhum oponente encontrado que voce enfrentou mais de uma vez.</p>'

        from datetime import datetime as _dt
        html = '<div class="cr-decks-list">'

        for i, opponent in enumerate(opponents, 1):
            tag       = opponent.get('tag', '')
            nome      = opponent.get('nome', 'Desconhecido')
            total     = opponent.get('total', 0)
            wins      = opponent.get('wins', 0)
            losses    = opponent.get('losses', 0)
            battles   = opponent.get('battles', [])
            last_deck = opponent.get('last_deck', '')

            draws = max(0, total - wins - losses)
            win_rate = round((wins / total * 100), 1) if total > 0 else 0

            wins_pct   = round((wins / total * 100), 1) if total > 0 else 0
            losses_pct = round((losses / total * 100), 1) if total > 0 else 0
            draws_pct  = round(max(0, 100 - wins_pct - losses_pct), 1)

            wr_color = '#48bb78' if win_rate >= 50 else '#f56565'

            # ---- Deck mais recente (grid 4+4) ----
            cards_section = ''
            if last_deck:
                cards_list = [c.strip() for c in last_deck.replace(' | ', '|').split('|')]
                cards_top  = cards_list[:4]
                cards_bot  = cards_list[4:8]

                def card_html(card_name, _self=self):
                    img_path = _self.get_card_image_path(card_name)
                    return (
                        '<div class="cr-card-wrap" title="' + card_name + '">'
                        '<img src="' + img_path + '" alt="' + card_name + '" class="cr-card-img" loading="lazy">'
                        '</div>'
                    )

                top_h = ''.join(card_html(c) for c in cards_top)
                bot_h = ''.join(card_html(c) for c in cards_bot)
                cards_section = (
                    '<div class="cr-cards-grid">'
                    '<div class="cr-opp-deck-label" style="font-size:0.7em;color:#718096;font-weight:600;margin-bottom:4px;text-transform:uppercase;">Ultimo deck visto:</div>'
                    '<div class="cr-cards-row">' + top_h + '</div>'
                    '<div class="cr-cards-row">' + bot_h + '</div>'
                    '</div>'
                )
            else:
                cards_section = '<div class="cr-no-deck" style="color:#a0aec0;font-size:0.8em;font-style:italic;width:270px;display:flex;align-items:center;justify-content:center;border:1px dashed #cbd5e0;border-radius:8px;">Deck nao disponível</div>'

            # ---- Timeline de batalhas com data e hora preservadas ----
            battles_html = ''
            for b in battles:
                resultado = b.get('resultado', '').lower()
                data_str  = b.get('data_str', '')

                try:
                    # Tenta converter se for string longa ou ja formatada
                    if '/' in data_str and ':' in data_str:
                        d_part = data_str.split(' ')[0]
                        h_part = data_str.split(' ')[1][:5]
                        data_fmt, hora_fmt = d_part[:5], h_part
                    else:
                        data_fmt, hora_fmt = data_str[:5], data_str[11:16]
                except Exception:
                    data_fmt, hora_fmt = data_str, ''

                if resultado in ['vitoria', 'victory']:
                    icone, cor, borda_c = 'V', '#48bb78', '#276749'
                elif resultado in ['derrota', 'defeat']:
                    icone, cor, borda_c = 'D', '#f56565', '#9b2c2c'
                else:
                    icone, cor, borda_c = 'E', '#ed8936', '#7b341e'

                battles_html += (
                    '<div class="cr-timeline-item" style="display:flex;flex-direction:column;align-items:center;gap:2px;">'
                    '<span class="cr-battle-badge" '
                    'style="background:' + cor + ';border-color:' + borda_c + ';margin:0;" '
                    'title="' + data_str + '">' + icone + '</span>'
                    '<span style="font-size:0.65em;color:#718096;font-weight:600;">' + data_fmt + '</span>'
                    '<span style="font-size:0.6em;color:#a0aec0;">' + hora_fmt + '</span>'
                    '</div>'
                )

            html += (
                '<div class="cr-deck-card">'
                '<div class="cr-deck-header">'
                '<div class="cr-deck-meta">'
                '<span class="cr-deck-rank">#' + str(i) + '</span>'
                '<span class="cr-deck-label" style="font-size:1em;color:#1a202c;font-weight:700;">' + nome + '</span>'
                '<span style="font-size:0.75em;color:#718096;">(' + tag + ')</span>'
                '</div>'
                '<span class="cr-wr-badge" style="background:' + wr_color + ';">' + str(win_rate) + '% WR</span>'
                '</div>'
                '<div class="cr-progress-bar" title="Vitorias ' + str(wins_pct) + '% | Derrotas ' + str(losses_pct) + '% | Empates ' + str(draws_pct) + '%">'
                '<div class="cr-bar-wins" style="width:' + str(wins_pct) + '%;"></div>'
                '<div class="cr-bar-draws" style="width:' + str(draws_pct) + '%;"></div>'
                '<div class="cr-bar-losses" style="width:' + str(losses_pct) + '%;"></div>'
                '</div>'
                '<div class="cr-deck-body">'
                + cards_section +
                '<div class="cr-stats-panel">'
                '<table class="cr-stats-table"><thead><tr>'
                '<th>WR%</th><th>Encontros</th>'
                '<th class="cr-th-win">Vitorias</th>'
                '<th class="cr-th-draw">Empates</th>'
                '<th class="cr-th-loss">Derrotas</th>'
                '</tr></thead><tbody><tr>'
                '<td style="color:' + wr_color + ';font-weight:700;">' + str(win_rate) + '%</td>'
                '<td>' + str(total) + 'x</td>'
                '<td class="cr-td-win">' + str(wins) + '</td>'
                '<td class="cr-td-draw">' + str(draws) + '</td>'
                '<td class="cr-td-loss">' + str(losses) + '</td>'
                '</tr></tbody></table>'
                '<div class="cr-battles-timeline">'
                '<span class="cr-timeline-label">Historico Detalhado:</span>'
                '<div class="cr-timeline-badges" style="display:flex;gap:8px;overflow-x:auto;padding-bottom:5px;">'
                + battles_html +
                '</div></div></div></div></div>'
            )

        html += '</div>'
        return html
'''

with open(TARGET_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Marcadores para localizar o metodo antigo
START_MARKER = '    def generate_repeated_opponents_html(self, opponents):'
# Procuramos o proximo metodo para definir o fim
END_MARKER = '    def get_repeated_opponents_from_csv(self)'

start_idx = content.find(START_MARKER)
end_idx = content.find(END_MARKER)

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + NEW_METHOD + '\n' + content[end_idx:]
    with open(TARGET_FILE, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("OK - Metodo de oponentes atualizado com sucesso!")
else:
    print(f"ERRO - Marcadores nao encontrados. Start: {start_idx}, End: {end_idx}")
