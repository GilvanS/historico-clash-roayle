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
<html lang="en">
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
        
        /* Clan Page Specific Styles */
        .page-header {
            text-align: center;
            margin-bottom: 20px;
        }
        
        .back-link {
            display: inline-block;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            text-decoration: none;
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: bold;
            margin-bottom: 20px;
            transition: background 0.3s ease;
        }
        
        .back-link:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        
        .clan-header {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
            backdrop-filter: blur(4px);
            border: 1px solid rgba(255, 255, 255, 0.18);
            text-align: center;
        }
        
        .clan-header h1 {
            color: #4a5568;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        
        .clan-info {
            color: #666;
            font-size: 1.1em;
        }
        
        /* Sortable table styles */
        .sortable {
            cursor: pointer;
            user-select: none;
            position: relative;
            transition: background-color 0.2s ease;
        }
        
        .sortable:hover {
            background-color: #3182ce !important;
        }
        
        .sort-indicator {
            font-size: 0.8em;
            margin-left: 5px;
            opacity: 0.6;
        }
        
        .sortable.sort-asc .sort-indicator:after {
            content: " ↑";
            color: #38a169;
            font-weight: bold;
        }
        
        .sortable.sort-desc .sort-indicator:after {
            content: " ↓";
            color: #e53e3e;
            font-weight: bold;
        }
        """
        
        return f"""
<!DOCTYPE html>
<html lang="en">
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
            <a href="index.html" class="back-link">← Back to Main Dashboard</a>
        </div>
        
        <div class="clan-header">
            <h1>🏰 {stats['clan_name'] or 'Clan Analytics'}</h1>
            <div class="clan-info">
                <p>Detailed clan statistics and member analytics</p>
                <p><strong>Your Position:</strong> Member since {self.format_date(stats.get('first_battle', ''))}</p>
            </div>
        </div>

        <!-- Clan Deck Analytics section - REMOVED for streamlined interface
        <div class="section">
            <h2>🃏 Clan Deck Analytics</h2>
            <p style="color: #666; margin-bottom: 15px; font-style: italic;">
                Popular decks, favorite cards, and deck experimentation patterns within your clan.
            </p>
            {clan_deck_analytics_html}
        </div>
        -->

        <!-- Clan Rankings & Progression section - REMOVED for cleaner interface
        <div class="section">
            <h2>🏆 Clan Rankings & Progression</h2>
            <p style="color: #666; margin-bottom: 15px; font-style: italic;">
                Current clan trophy rankings with recent changes. Green = trophy gains, red = trophy losses.
            </p>
            {clan_rankings_html}
        </div>
        -->

        <div class="section">
            <h2>🏰 Clan Member Activity</h2>
            <p style="color: #666; margin-bottom: 15px; font-style: italic;">
                Click on any member name to view their detailed deck change history.
            </p>
            <div class="desktop-table">
                <table id="clan-members-table">
                    <thead>
                        <tr>
                            <th class="sortable" data-column="name">Name <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="role">Role <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="trophies">Trophies <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="donations">Donations <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="deck-changes">Deck Changes <span class="sort-indicator">↕</span></th>
                            <th class="sortable" data-column="last-seen">Last Seen <span class="sort-indicator">↕</span></th>
                        </tr>
                    </thead>
                    <tbody>{clan_table_html}</tbody>
                </table>
            </div>
            <div class="clan-member-cards">{clan_cards_html}</div>
        </div>

        <div class="footer">
            <p>Clan report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Data last updated: {self.format_time_ago(stats['last_updated'])}</p>
            <p><a href="index.html" class="back-link">← Back to Main Dashboard</a></p>
        </div>
    </div>
    
    <script>
    // Table sorting functionality
    document.addEventListener('DOMContentLoaded', function() {{
        var table = document.getElementById('clan-members-table');
        var headers = table.querySelectorAll('th.sortable');
        var currentSort = {{ column: '', direction: '' }};
        
        headers.forEach(function(header) {{
            header.addEventListener('click', function() {{
                var column = this.getAttribute('data-column');
                var direction = currentSort.column === column && currentSort.direction === 'asc' ? 'desc' : 'asc';
                
                // Remove existing sort classes
                headers.forEach(function(h) {{ h.classList.remove('sort-asc', 'sort-desc'); }});
                
                // Add sort class to current header
                this.classList.add('sort-' + direction);
                
                // Sort the table
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
                        // Custom role order: leader > co-leader > elder > member
                        var roleOrder = {{'leader': 1, 'co-leader': 2, 'elder': 3, 'member': 4}};
                        aVal = roleOrder[a.cells[1].textContent.trim().toLowerCase()] || 5;
                        bVal = roleOrder[b.cells[1].textContent.trim().toLowerCase()] || 5;
                        break;
                    case 'trophies':
                        aVal = parseInt(a.cells[2].textContent.replace(/,/g, '')) || 0;
                        bVal = parseInt(b.cells[2].textContent.replace(/,/g, '')) || 0;
                        break;
                    case 'donations':
                        // Extract total donations (sent + received)
                        var aDonations = a.cells[3].textContent.match(/(\\d+)↑\\s*(\\d+)↓/);
                        var bDonations = b.cells[3].textContent.match(/(\\d+)↑\\s*(\\d+)↓/);
                        aVal = aDonations ? parseInt(aDonations[1]) + parseInt(aDonations[2]) : 0;
                        bVal = bDonations ? parseInt(bDonations[1]) + parseInt(bDonations[2]) : 0;
                        break;
                    case 'deck-changes':
                        aVal = parseInt(a.cells[4].textContent) || 0;
                        bVal = parseInt(b.cells[4].textContent) || 0;
                        break;
                    case 'last-seen':
                        // Parse relative time strings for sorting
                        aVal = parseTimeAgo(a.cells[5].textContent.trim());
                        bVal = parseTimeAgo(b.cells[5].textContent.trim());
                        break;
                    default:
                        aVal = a.cells[0].textContent.trim();
                        bVal = b.cells[0].textContent.trim();
                }}
                
                if (direction === 'asc') {{
                    return aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
                }} else {{
                    return aVal > bVal ? -1 : aVal < bVal ? 1 : 0;
                }}
            }});
            
            // Re-append sorted rows
            rows.forEach(function(row) {{ tbody.appendChild(row); }});
        }}
        
        function parseTimeAgo(timeStr) {{
            // Convert time ago strings to minutes for sorting
            if (timeStr === 'never') return 999999;
            if (timeStr.includes('hours ago')) {{
                return parseInt(timeStr) * 60;
            }} else if (timeStr.includes('days ago')) {{
                return parseInt(timeStr) * 24 * 60;
            }} else if (timeStr.includes('minutes ago')) {{
                return parseInt(timeStr);
            }} else if (timeStr.includes('hour ago')) {{
                return 60;
            }} else if (timeStr.includes('day ago')) {{
                return 24 * 60;
            }} else if (timeStr.includes('minute ago')) {{
                return 1;
            }}
            return 0; // "just now" or unrecognized format
        }}
    }});
    </script>
</body>
</html>
        """
    
    def get_base_css_styles(self) -> str:
        """Get the base CSS styles (extracted from main generator)"""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
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
            font-family: 'Clash-Regular', 'Supercell-Magic', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .section {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
            backdrop-filter: blur(4px);
            border: 1px solid rgba(255, 255, 255, 0.18);
        }
        
        .section h2 {
            color: #2d3748;
            margin-bottom: 25px;
            border-bottom: 3px solid #4299e1;
            padding-bottom: 10px;
        }
        
        /* Include all the existing clan ranking and deck analytics styles from the main CSS */
        .clan-rankings { display: flex; flex-direction: column; gap: 12px; }
        .ranking-item { display: flex; align-items: center; background: rgba(255, 255, 255, 0.9); border-radius: 10px; padding: 15px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); transition: transform 0.2s ease; }
        .ranking-item:hover { transform: translateY(-2px); }
        .current-player-ranking { background: rgba(66, 153, 225, 0.15); border-left: 4px solid #4299e1; font-weight: bold; }
        .ranking-position { font-size: 1.5em; font-weight: bold; color: #4299e1; min-width: 50px; text-align: center; }
        .ranking-info { flex: 1; margin-left: 20px; }
        .ranking-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .ranking-stats { display: flex; gap: 20px; align-items: center; flex-wrap: wrap; }
        .stat-group { display: flex; align-items: center; gap: 8px; }
        .trophy-up { color: #38a169; font-weight: bold; font-size: 0.9em; }
        .trophy-down { color: #e53e3e; font-weight: bold; font-size: 0.9em; }
        .trophy-neutral { color: #718096; font-size: 0.9em; }
        .donation-up { color: #3182ce; font-weight: bold; font-size: 0.9em; }
        .donation-down { color: #e53e3e; font-weight: bold; font-size: 0.9em; }
        .donation-neutral { color: #718096; font-size: 0.9em; }
        .last-seen-info { color: #718096; font-size: 0.9em; }
        
        /* Deck analytics styles */
        .analytics-section { margin-bottom: 30px; }
        .analytics-section h3 { color: #2d3748; margin-bottom: 15px; font-size: 1.2em; }
        .popular-deck-item { background: rgba(255, 255, 255, 0.9); border-radius: 10px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); }
        .deck-popularity { display: flex; align-items: center; margin-bottom: 10px; }
        .deck-rank { font-size: 1.5em; font-weight: bold; color: #4299e1; min-width: 40px; }
        .deck-info { margin-left: 15px; }
        .usage-count { font-weight: bold; color: #2d3748; }
        .users-list { color: #718096; font-size: 0.9em; display: block; }
        .favorite-cards-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 15px; }
        .favorite-card-item { background: rgba(255, 255, 255, 0.9); border-radius: 10px; padding: 10px; text-align: center; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); }
        .favorite-card-image { width: 50px; height: 60px; object-fit: contain; margin-bottom: 8px; }
        .favorite-card-info .card-name { display: block; font-weight: 500; color: #2d3748; font-size: 0.9em; }
        .favorite-card-info .usage-count { color: #4299e1; font-size: 0.8em; }
        .experimenters-list { display: flex; flex-direction: column; gap: 8px; }
        .experimenter-item { display: flex; justify-content: space-between; align-items: center; background: rgba(255, 255, 255, 0.9); border-radius: 8px; padding: 10px 15px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1); }
        .experimenter-item .member-name { font-weight: 500; color: #2d3748; }
        .experimenter-item .change-count { color: #4299e1; font-size: 0.9em; font-weight: bold; }
        
        /* Deck cards styles */
        .deck-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 15px; }
        .card-container { text-align: center; background: rgba(255, 255, 255, 0.9); border-radius: 8px; padding: 10px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); }
        .card-image { width: 60px; height: 72px; object-fit: contain; border-radius: 5px; }
        .card-name { font-size: 0.8em; margin-top: 5px; color: #4a5568; font-weight: 500; }
        
        /* Table styles */
        table { width: 100%; border-collapse: collapse; background: rgba(255, 255, 255, 0.9); border-radius: 8px; overflow: hidden; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #e2e8f0; }
        th { background: #4299e1; color: white; font-weight: 600; }
        .current-player { background-color: rgba(66, 153, 225, 0.2); font-weight: bold; }
        .role-leader { color: #d69e2e; font-weight: bold; }
        .role-co-leader { color: #3182ce; font-weight: bold; }
        .role-elder { color: #38a169; font-weight: bold; }
        .role-member { color: #718096; }
        
        /* Mobile styles */
        .clan-member-cards { display: none; }
        .clan-member-card { background: rgba(255, 255, 255, 0.9); border-radius: 10px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); border-left: 4px solid #e2e8f0; }
        .current-player-card { border-left-color: #4299e1; background: rgba(66, 153, 225, 0.1); }
        .member-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .member-name { font-size: 1.1em; color: #2d3748; }
        .member-role { padding: 3px 8px; border-radius: 5px; background: rgba(255, 255, 255, 0.8); font-size: 0.9em; font-weight: bold; }
        .member-card-content { display: flex; justify-content: space-between; align-items: center; }
        .member-stats { display: flex; flex-direction: column; gap: 5px; }
        .trophy-count, .donation-stats { padding: 3px 8px; border-radius: 5px; background: rgba(255, 255, 255, 0.8); font-size: 0.9em; }
        .member-activity { text-align: right; }
        .last-seen { color: #718096; font-size: 0.9em; padding: 3px 8px; border-radius: 5px; background: rgba(255, 255, 255, 0.8); }
        
        .footer { text-align: center; color: rgba(255, 255, 255, 0.8); margin-top: 30px; font-size: 0.9em; }
        
        @media (max-width: 768px) {
            .deck-cards { grid-template-columns: repeat(2, 1fr); }
            .desktop-table { display: none; }
            .clan-member-cards { display: block; }
            .container { padding: 10px; }
            .section { padding: 20px; }
            .ranking-stats { flex-direction: column; align-items: flex-start; gap: 8px; }
            .ranking-header { flex-direction: column; align-items: flex-start; gap: 5px; }
        }
        
        @media (min-width: 769px) {
            .desktop-table { display: block; }
            .clan-member-cards { display: none; }
        }
        """

def main():
    """Generate clan analytics HTML report"""
    generator = ClanAnalyticsGenerator()
    html_content = generator.generate_clan_html_report()
    
    # Ensure docs directory exists
    os.makedirs('../docs', exist_ok=True)
    
    # Save as clan.html for GitHub Pages in docs directory
    with open('../docs/clan.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("Clan analytics HTML report generated: ../docs/clan.html")

if __name__ == "__main__":
    main()