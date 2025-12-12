#!/usr/bin/env python3
"""
Individual Member HTML Generator for GitHub Pages
Generates detailed member pages with deck change tracking
"""

import sqlite3
import os
import re
from datetime import datetime
from typing import List, Dict, Optional
from html_generator import GitHubPagesHTMLGenerator

class MemberPageGenerator(GitHubPagesHTMLGenerator):
    def __init__(self, db_path: str = "clash_royale.db"):
        super().__init__(db_path)
    
    def get_member_deck_history(self, player_tag: str) -> List[Dict]:
        """Get complete deck change history for a member, consolidating consecutive identical decks"""
        if not os.path.exists(self.db_path):
            return []
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clan_member_decks'")
        if not cursor.fetchone():
            conn.close()
            return []
        
        cursor.execute("""
            SELECT 
                deck_cards,
                favorite_card,
                arena_name,
                league_name,
                exp_level,
                trophies,
                best_trophies,
                first_seen,
                last_seen
            FROM clan_member_decks 
            WHERE player_tag = ?
            ORDER BY first_seen ASC
        """, (player_tag,))
        
        raw_history = []
        for row in cursor.fetchall():
            raw_history.append({
                'deck_cards': row[0],
                'favorite_card': row[1],
                'arena_name': row[2],
                'league_name': row[3],
                'exp_level': row[4],
                'trophies': row[5],
                'best_trophies': row[6],
                'first_seen': row[7],
                'last_seen': row[8]
            })
        
        conn.close()
        
        # Consolidate consecutive identical decks (same deck_cards)
        consolidated_history = []
        current_deck = None
        
        for record in raw_history:
            if current_deck is None or current_deck['deck_cards'] != record['deck_cards']:
                # Start a new deck period
                if current_deck is not None:
                    # Finalize the previous deck
                    duration = self.calculate_deck_duration(current_deck['first_seen'], current_deck['last_seen'])
                    current_deck['duration'] = duration
                    consolidated_history.append(current_deck)
                
                # Start new deck period
                current_deck = record.copy()
            else:
                # Same deck, extend the period and update latest info
                current_deck['last_seen'] = record['last_seen']
                current_deck['favorite_card'] = record['favorite_card']  # Use most recent favorite card
                current_deck['arena_name'] = record['arena_name']
                current_deck['league_name'] = record['league_name']
                current_deck['exp_level'] = record['exp_level']
                current_deck['trophies'] = record['trophies']
                current_deck['best_trophies'] = record['best_trophies']
        
        # Don't forget the last deck
        if current_deck is not None:
            duration = self.calculate_deck_duration(current_deck['first_seen'], current_deck['last_seen'])
            current_deck['duration'] = duration
            consolidated_history.append(current_deck)
        
        # Return in reverse chronological order (most recent first)
        return list(reversed(consolidated_history))
    
    def calculate_deck_duration(self, first_seen: str, last_seen: str) -> str:
        """Calculate how long a deck was used"""
        if not first_seen or not last_seen:
            return "Unknown"
        
        try:
            start = datetime.fromisoformat(first_seen.replace('Z', '+00:00'))
            end = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
            duration = end - start
            
            if duration.days > 0:
                return f"{duration.days} day{'s' if duration.days > 1 else ''}"
            elif duration.seconds > 3600:
                hours = duration.seconds // 3600
                return f"{hours} hour{'s' if hours > 1 else ''}"
            elif duration.seconds > 60:
                minutes = duration.seconds // 60
                return f"{minutes} minute{'s' if minutes > 1 else ''}"
            else:
                return "Less than a minute"
        except:
            return "Unknown"
    
    def get_member_info(self, player_tag: str) -> Optional[Dict]:
        """Get member basic info"""
        if not os.path.exists(self.db_path):
            return None
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name, role, trophies, donations, donations_received, last_seen
            FROM clan_members 
            WHERE player_tag = ?
        """, (player_tag,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        
        member_info = {
            'player_tag': player_tag,
            'name': row[0],
            'role': row[1],
            'trophies': row[2] or 0,
            'donations': row[3] or 0,
            'donations_received': row[4] or 0,
            'last_seen': row[5]
        }
        
        conn.close()
        return member_info
    
    def safe_filename(self, name: str) -> str:
        """Convert member name to safe filename"""
        # Remove special characters and spaces
        safe_name = re.sub(r'[^\w\s-]', '', name)
        safe_name = re.sub(r'\s+', '_', safe_name)
        return safe_name.lower()
    
    def generate_member_page(self, player_tag: str) -> str:
        """Generate individual member page HTML"""
        member_info = self.get_member_info(player_tag)
        if not member_info:
            return self.generate_member_error_page()
        
        deck_history = self.get_member_deck_history(player_tag)
        
        return self.generate_member_full_html(member_info, deck_history)
    
    def generate_member_error_page(self) -> str:
        """Generate error page when member data is not available"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Member Profile - No Data</title>
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
        <h1>👤 Member Profile</h1>
        <h2>No Member Data Available</h2>
        <p>Member data is being generated. Please check back in a few minutes.</p>
        <p><a href="clan.html" class="back-link">← Back to Clan Analytics</a></p>
    </div>
</body>
</html>
        """
    
    def generate_deck_timeline_html(self, deck_history: List[Dict]) -> str:
        """Generate HTML timeline of deck changes"""
        if not deck_history:
            return "<p>No deck history available yet.</p>"
        
        timeline_html = '<div class="deck-timeline">'
        
        for i, deck in enumerate(deck_history):
            is_current = i == 0  # First item is most recent
            timeline_class = "timeline-current" if is_current else "timeline-past"
            
            deck_cards_html = self.generate_deck_cards_html(deck['deck_cards'], show_names=False)
            
            timeline_html += f'''
                <div class="timeline-item {timeline_class}">
                    <div class="timeline-marker">
                        <div class="timeline-date">{self.format_date(deck['first_seen'])}</div>
                        <div class="timeline-duration">{deck['duration']}</div>
                    </div>
                    <div class="timeline-content">
                        <div class="deck-header">
                            <h3>{'Current Deck' if is_current else 'Previous Deck'}</h3>
                            <div class="deck-stats">
                                <span class="stat">⭐ {deck['favorite_card'] or 'None'}</span>
                                <span class="stat">🏆 {deck['trophies']:,}</span>
                                <span class="stat">🏟️ {deck['arena_name'] or 'Unknown'}</span>
                            </div>
                        </div>
                        {deck_cards_html}
                    </div>
                </div>
            '''
        
        timeline_html += '</div>'
        return timeline_html
    
    def generate_member_full_html(self, member_info: Dict, deck_history: List[Dict]) -> str:
        """Generate the complete member page HTML"""
        
        role_class = {
            'leader': 'leader',
            'coLeader': 'co-leader', 
            'elder': 'elder',
            'member': 'member'
        }.get(member_info['role'], 'member')
        
        role_display = member_info['role'].replace('coLeader', 'Co-Leader')
        
        deck_timeline_html = self.generate_deck_timeline_html(deck_history)
        
        css_styles = self.get_base_css_styles() + """
        
        /* Member Page Specific Styles */
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
        
        .member-header {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
            backdrop-filter: blur(4px);
            border: 1px solid rgba(255, 255, 255, 0.18);
            text-align: center;
        }
        
        .member-header h1 {
            color: #4a5568;
            margin-bottom: 15px;
            font-size: 2.5em;
        }
        
        .member-role {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            margin-bottom: 15px;
        }
        
        .role-leader { background: #d69e2e; color: white; }
        .role-co-leader { background: #3182ce; color: white; }
        .role-elder { background: #38a169; color: white; }
        .role-member { background: #718096; color: white; }
        
        .member-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .member-stat {
            background: rgba(255, 255, 255, 0.8);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        
        .member-stat .value {
            font-size: 1.5em;
            font-weight: bold;
            color: #4299e1;
        }
        
        .member-stat .label {
            color: #666;
            font-size: 0.9em;
        }
        
        /* Timeline Styles */
        .deck-timeline {
            position: relative;
            padding-left: 30px;
        }
        
        .deck-timeline::before {
            content: '';
            position: absolute;
            left: 15px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #e2e8f0;
        }
        
        .timeline-item {
            position: relative;
            margin-bottom: 30px;
            background: rgba(255, 255, 255, 0.9);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }
        
        .timeline-current {
            border-left: 4px solid #38a169;
        }
        
        .timeline-past {
            border-left: 4px solid #cbd5e0;
        }
        
        .timeline-marker {
            position: absolute;
            left: -45px;
            top: 20px;
            text-align: center;
            background: white;
            padding: 5px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        .timeline-date {
            font-size: 0.8em;
            color: #4299e1;
            font-weight: bold;
        }
        
        .timeline-duration {
            font-size: 0.7em;
            color: #718096;
        }
        
        .deck-header {
            margin-bottom: 15px;
        }
        
        .deck-header h3 {
            color: #2d3748;
            margin-bottom: 8px;
        }
        
        .deck-stats {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        
        .stat {
            background: rgba(255, 255, 255, 0.8);
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 0.9em;
        }
        
        @media (max-width: 768px) {
            .member-stats { grid-template-columns: 1fr; }
            .deck-stats { flex-direction: column; gap: 8px; }
            .timeline-marker { left: -35px; }
        }
        """
        
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Member Profile - {member_info['name']}</title>
    <link rel="icon" type="image/x-icon" href="/favicon.ico">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
    <style>{css_styles}</style>
</head>
<body>
    <div class="container">
        <div class="page-header">
            <a href="clan.html" class="back-link">← Back to Clan Analytics</a>
        </div>
        
        <div class="member-header">
            <h1>👤 {member_info['name']}</h1>
            <div class="member-role role-{role_class}">{role_display}</div>
            <div class="member-stats">
                <div class="member-stat">
                    <div class="value">{member_info['trophies']:,}</div>
                    <div class="label">Current Trophies</div>
                </div>
                <div class="member-stat">
                    <div class="value">{member_info['donations']}</div>
                    <div class="label">Donations Given</div>
                </div>
                <div class="member-stat">
                    <div class="value">{member_info['donations_received']}</div>
                    <div class="label">Donations Received</div>
                </div>
                <div class="member-stat">
                    <div class="value">{len(deck_history)}</div>
                    <div class="label">Deck Changes</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>🃏 Deck Change Timeline</h2>
            <p style="color: #666; margin-bottom: 15px; font-style: italic;">
                Complete history of deck changes and favorite card preferences.
            </p>
            {deck_timeline_html}
        </div>

        <div class="footer">
            <p>Member profile generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Last seen: {self.format_time_ago(member_info['last_seen'])}</p>
            <p><a href="clan.html" class="back-link">← Back to Clan Analytics</a></p>
        </div>
    </div>
</body>
</html>
        """

def main():
    """Generate member pages for all clan members"""
    generator = MemberPageGenerator()
    
    # Get all clan members
    if not os.path.exists("clash_royale.db"):
        print("Database not found")
        return
    
    conn = sqlite3.connect("clash_royale.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT player_tag, name FROM clan_members")
    members = cursor.fetchall()
    conn.close()
    
    if not members:
        print("No clan members found")
        return
    
    # Ensure docs directory exists
    os.makedirs('../docs', exist_ok=True)
    
    generated_pages = []
    
    for player_tag, name in members:
        html_content = generator.generate_member_page(player_tag)
        filename = f"member_{generator.safe_filename(name)}.html"
        filepath = f"../docs/{filename}"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        generated_pages.append((name, filename))
        print(f"Generated: ../docs/{filename}")
    
    print(f"Generated {len(generated_pages)} member pages")
    return generated_pages

if __name__ == "__main__":
    main()