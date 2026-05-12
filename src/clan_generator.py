#!/usr/bin/env python3
"""
Clan Analytics HTML Generator for GitHub Pages
Generates dedicated clan statistics page
"""

import sqlite3
import os
import re
from datetime import datetime
from typing import List, Dict, Optional
from html_generator import GitHubPagesHTMLGenerator

class ClanAnalyticsGenerator(GitHubPagesHTMLGenerator):
    def __init__(self, db_path: str = "clash_royale.db"):
        super().__init__(db_path)
    
    def safe_filename(self, name: str) -> str:
        """Convert member name to safe filename"""
        # Remove special characters and spaces
        safe_name = re.sub(r'[^\w\s-]', '', name)
        safe_name = re.sub(r'\s+', '_', safe_name)
        return safe_name.lower()
    
    def generate_clan_html_report(self) -> str:
        """Generate complete clan analytics HTML report"""
        stats = self.get_player_stats()
        clan_rankings = self.get_clan_rankings_data()
        deck_analytics = self.get_clan_deck_analytics()
        clan_members = self.get_clan_members()
        
        if not stats:
            return self.generate_clan_error_page()
        
        # Generate HTML sections
        clan_rankings_html = self.generate_clan_rankings_html(clan_rankings, stats['name'])
        clan_deck_analytics_html = self.generate_clan_deck_analytics_html(deck_analytics)
        
        # Create deck changes lookup
        deck_changes_lookup = {}
        if deck_analytics and 'deck_experimenters' in deck_analytics:
            for experimenter in deck_analytics['deck_experimenters']:
                deck_changes_lookup[experimenter['name']] = experimenter['deck_changes']
        
        # Generate clan member tables/cards (reuse existing logic)
        clan_table_html = ""
        clan_cards_html = ""
        
        for member in clan_members[:20]:
            is_current_player = member['name'] == stats['name']
            row_class = "current-player" if is_current_player else ""
            card_class = "current-player-card" if is_current_player else ""
            
            role_class = {
                'leader': 'leader',
                'coLeader': 'co-leader', 
                'elder': 'elder',
                'member': 'member'
            }.get(member['role'], 'member')
            
            role_display = member['role'].replace('coLeader', 'Co-Leader')
            
            member_filename = f"member_{self.safe_filename(member['name'])}.html"
            member_link = f'<a href="{member_filename}" style="color: #4299e1; text-decoration: none; font-weight: bold;">{member["name"]}</a>'
            
            # Get deck changes for this member
            deck_changes = deck_changes_lookup.get(member['name'], 0)
            
            clan_table_html += f"""
                <tr class="{row_class}">
                    <td>{member_link}</td>
                    <td><span class="role-{role_class}">{role_display}</span></td>
                    <td>{member['trophies']:,}</td>
                    <td>{member['donations']}↑ {member['donations_received']}↓</td>
                    <td>{deck_changes}</td>
                    <td>{self.format_time_ago(member['last_seen'])}</td>
                </tr>
            """
            
            clan_cards_html += f"""
                <div class="clan-member-card {card_class}">
                    <div class="member-card-header">
                        <strong class="member-name">{member_link}</strong>
                        <span class="role-{role_class} member-role">{role_display}</span>
                    </div>
                    <div class="member-card-content">
                        <div class="member-stats">
                            <span class="trophy-count">🏆 {member['trophies']:,}</span>
                            <span class="donation-stats">📦 {member['donations']}↑ {member['donations_received']}↓</span>
                            <span class="deck-changes">🔄 {deck_changes} deck changes</span>
                        </div>
                        <div class="member-activity">
                            <span class="last-seen">🕒 {self.format_time_ago(member['last_seen'])}</span>
                        </div>
                    </div>
                </div>
            """
        
        return self.generate_clan_full_html(stats, clan_rankings_html, clan_deck_analytics_html, 
                                          clan_table_html, clan_cards_html)
    
    def generate_clan_error_page(self) -> str:
        """Generate error page when no clan data is available"""
        return """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clan Analytics - No Data</title>
    <style>
        @font-face {
            font-family: 'Clash-Regular';
            src: url('assets/fonts/Clash_Regular.otf') format('opentype');
            font-weight: normal;
            font-style: normal;
        }
        
        @font-face {
            font-family: 'Supercell-Magic';
            src: url('assets/fonts/Supercell-Magic Regular.ttf') format('truetype');
            font-weight: normal;
            font-style: normal;
        }
        
        body { 
            font-family: 'Clash-Regular', 'Supercell-Magic', Arial, sans-serif; 
            text-align: center; 
            padding: 50px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .error-container {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 40px;
            max-width: 600px;
            margin: 0 auto;
        }
        .back-link {
            color: #4299e1;
            text-decoration: none;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="error-container">
        <h1>🏰 Clan Analytics</h1>
        <h2>No Clan Data Available</h2>
        <p>Clan analytics data is being generated. Please check back in a few minutes.</p>
        <p><a href="index.html" class="back-link">← Back to Main Dashboard</a></p>
    </div>
</body>
</html>
        """
    
    def generate_clan_full_html(self, stats, clan_rankings_html, clan_deck_analytics_html,
                               clan_table_html, clan_cards_html) -> str:
        """Generate the complete clan analytics HTML document"""
        
        # Reuse the main CSS styles from parent class but add clan-specific styles
        css_styles = self.get_base_css_styles() + """
        
        /* Clan Page Specific Styles - Premium v2 */
        .page-header {
            text-align: left;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
        }
        
        .back-link {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: var(--glass-bg);
            color: #fff;
            text-decoration: none;
            padding: 12px 24px;
            border-radius: 50px;
            font-weight: 700;
            font-family: 'Outfit', sans-serif;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-size: 0.85em;
            border: 1px solid var(--glass-border);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: var(--card-shadow);
        }
        
        .back-link:hover {
            background: rgba(30, 41, 59, 0.8);
            border-color: var(--primary);
            transform: translateX(-5px);
            box-shadow: 0 0 20px var(--primary-glow);
        }
        
        .clan-header {
            padding: 50px 40px;
            margin-bottom: 40px;
            text-align: center;
            position: relative;
            overflow: hidden;
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 24px;
            box-shadow: var(--card-shadow);
        }
        
        .clan-header h1 {
            font-size: 3em;
            margin-bottom: 15px;
            background: linear-gradient(135deg, #fff 0%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 4px 12px rgba(0,0,0,0.5));
        }
        
        .clan-info {
            color: #94a3b8;
            font-size: 1.1em;
            font-weight: 500;
        }

        .clan-info strong {
            color: var(--primary);
        }
        
        /* Sortable table styles Premium v2 */
        table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0 10px;
            margin-top: -10px;
        }

        thead th {
            background: transparent;
            color: #64748b;
            font-family: 'Outfit', sans-serif;
            text-transform: uppercase;
            font-size: 0.75em;
            letter-spacing: 1px;
            padding: 15px 20px;
            border: none;
            text-align: left;
        }

        tbody tr {
            background: rgba(30, 41, 59, 0.4);
            transition: all 0.3s ease;
            cursor: pointer;
        }

        tbody tr:hover {
            background: rgba(30, 41, 59, 0.8);
            transform: scale(1.005) translateY(-2px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }

        tbody td {
            padding: 20px;
            border: 1px solid transparent;
            border-top: 1px solid var(--glass-border);
            border-bottom: 1px solid var(--glass-border);
            color: #e2e8f0;
        }

        tbody td:first-child {
            border-left: 1px solid var(--glass-border);
            border-radius: 16px 0 0 16px;
        }

        tbody td:last-child {
            border-right: 1px solid var(--glass-border);
            border-radius: 0 16px 16px 0;
        }

        .current-player {
            background: rgba(66, 153, 225, 0.1) !important;
            border-color: var(--primary) !important;
        }

        .current-player td {
            border-top-color: var(--primary);
            border-bottom-color: var(--primary);
        }

        .current-player td:first-child { border-left-color: var(--primary); }
        .current-player td:last-child { border-right-color: var(--primary); }

        .sortable {
            cursor: pointer;
            transition: color 0.2s ease;
        }
        
        .sortable:hover {
            color: var(--primary);
        }
        
        .sort-indicator {
            font-size: 0.9em;
            margin-left: 5px;
            opacity: 0.4;
        }
        
        .sortable.sort-asc .sort-indicator { opacity: 1; color: var(--success); }
        .sortable.sort-desc .sort-indicator { opacity: 1; color: var(--danger); }

        .role-leader { color: #f6ad55; font-weight: 800; text-transform: uppercase; font-size: 0.8em; }
        .role-co-leader { color: #4299e1; font-weight: 800; text-transform: uppercase; font-size: 0.8em; }
        .role-elder { color: #48bb78; font-weight: 800; text-transform: uppercase; font-size: 0.8em; }
        .role-member { color: #94a3b8; font-weight: 800; text-transform: uppercase; font-size: 0.8em; }
        
        /* Mobile cards Premium v2 */
        .clan-member-card {
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: var(--card-shadow);
            transition: all 0.3s ease;
        }

        .clan-member-card:hover {
            transform: translateY(-5px);
            border-color: var(--primary);
        }

        .member-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--glass-border);
            padding-bottom: 15px;
        }

        .member-name a {
            font-family: 'Outfit', sans-serif;
            font-size: 1.2em;
            color: #fff !important;
            text-decoration: none;
        }

        .member-stats {
            display: grid !important;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }

        .trophy-count, .donation-stats, .deck-changes, .last-seen {
            background: rgba(0,0,0,0.2);
            padding: 10px 15px;
            border-radius: 12px;
            font-size: 0.85em;
            color: #cbd5e0;
            display: flex;
            align-items: center;
            gap: 8px;
            border: 1px solid rgba(255,255,255,0.03);
        }

        .member-activity {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid var(--glass-border);
        }
        
        .footer { 
            text-align: center; 
            color: #64748b; 
            margin-top: 60px; 
            padding: 40px;
            border-top: 1px solid var(--glass-border);
            font-size: 0.9em; 
        }

        /* Override links */
        a { transition: all 0.3s ease; }
        a:hover { filter: brightness(1.2); text-shadow: 0 0 10px var(--primary-glow); }
        """
        
        return f"""
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clan Analytics - {stats['clan_name'] or 'Unknown Clan'}</title>
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
    <style>{css_styles}</style>
</head>
<body>
    <div class="container">
        <div class="page-header">
            <a href="index.html" class="back-link">← Voltar ao Painel Principal</a>
        </div>
        
        <div class="clan-header">
            <h1>🏰 {stats['clan_name'] or 'Clan Analytics'}</h1>
            <div class="clan-info">
                <p>Estatísticas detalhadas e análise de membros do clã</p>
                <p>Sua jornada começou em <strong>{self.format_date(stats.get('first_battle', ''))}</strong></p>
            </div>
        </div>

        <div class="section">
            <h2>📊 Atividade dos Membros</h2>
            <div class="desktop-table">
                <table id="clan-members-table">
                    <thead>
                        <tr>
                            <th class="sortable" data-column="name">Membro <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="role">Cargo <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="trophies">Troféus <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="donations">Doações <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="deck-changes">Trocas de Deck <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="last-seen">Visto por último <span class="sort-indicator">↕</span></th>
                        </tr>
                    </thead>
                    <tbody>{clan_table_html}</tbody>
                </table>
            </div>
            <div class="clan-member-cards">{clan_cards_html}</div>
        </div>

        <div class="footer">
            <p>Relatório gerado em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Última atualização dos dados: {self.format_time_ago(stats['last_updated'])}</p>
            <div style="margin-top: 20px;">
                <a href="index.html" class="back-link">← Dashboard</a>
            </div>
        </div>
    </div>
    
    <script>
    // Table sorting functionality Premium v2
    document.addEventListener('DOMContentLoaded', function() {{
        var table = document.getElementById('clan-members-table');
        if(!table) return;

        var headers = table.querySelectorAll('th.sortable');
        var currentSort = {{ column: '', direction: '' }};
        
        headers.forEach(function(header) {{
            header.addEventListener('click', function() {{
                var column = this.getAttribute('data-column');
                var direction = currentSort.column === column && currentSort.direction === 'asc' ? 'desc' : 'asc';
                
                headers.forEach(function(h) {{ h.classList.remove('sort-asc', 'sort-desc'); }});
                this.classList.add('sort-' + direction);
                
                sortTable(column, direction);
                currentSort = {{ column: column, direction: direction }};
            }});
        }});
        
        function sortTable(column, direction) {{
            var tbody = table.querySelector('tbody');
            var rows = Array.from(tbody.querySelectorAll('tr'));
            
            rows.sort(function(a, b) {{
                var aVal, bVal;
                
                switch(column) {{
                    case 'name':
                        aVal = a.cells[0].textContent.trim().toLowerCase();
                        bVal = b.cells[0].textContent.trim().toLowerCase();
                        break;
                    case 'role':
                        var roleOrder = {{'leader': 1, 'co-leader': 2, 'elder': 3, 'member': 4}};
                        aVal = roleOrder[a.cells[1].textContent.trim().toLowerCase()] || 5;
                        bVal = roleOrder[b.cells[1].textContent.trim().toLowerCase()] || 5;
                        break;
                    case 'trophies':
                        aVal = parseInt(a.cells[2].textContent.replace(/,/g, '')) || 0;
                        bVal = parseInt(b.cells[2].textContent.replace(/,/g, '')) || 0;
                        break;
                    case 'donations':
                        var aDonations = a.cells[3].textContent.match(/(\\d+)↑/);
                        var bDonations = b.cells[3].textContent.match(/(\\d+)↑/);
                        aVal = aDonations ? parseInt(aDonations[1]) : 0;
                        bVal = bDonations ? parseInt(bDonations[1]) : 0;
                        break;
                    case 'deck-changes':
                        aVal = parseInt(a.cells[4].textContent) || 0;
                        bVal = parseInt(b.cells[4].textContent) || 0;
                        break;
                    case 'last-seen':
                        aVal = parseTimeAgo(a.cells[5].textContent.trim());
                        bVal = parseTimeAgo(b.cells[5].textContent.trim());
                        break;
                    default:
                        aVal = a.cells[0].textContent.trim();
                        bVal = b.cells[0].textContent.trim();
                }}
                
                return direction === 'asc' ? (aVal < bVal ? -1 : 1) : (aVal > bVal ? -1 : 1);
            }});
            
            rows.forEach(function(row) {{ tbody.appendChild(row); }});
        }}
        
        function parseTimeAgo(timeStr) {{
            if (timeStr.includes('never') || timeStr.includes('nunca')) return 999999;
            var num = parseInt(timeStr) || 0;
            if (timeStr.includes('day') || timeStr.includes('dia')) return num * 1440;
            if (timeStr.includes('hour') || timeStr.includes('hora')) return num * 60;
            return num;
        }}
    }});
    </script>
</body>
</html>
        """


def main():
    """Generate clan analytics HTML report"""
    # Get the repository root directory (one level up from src)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    
    generator = ClanAnalyticsGenerator()
    html_content = generator.generate_clan_html_report()
    
    # Save as clan.html in root directory
    filepath = os.path.join(root_dir, 'clan.html')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Clan analytics HTML report generated: {filepath}")

if __name__ == "__main__":
    main()