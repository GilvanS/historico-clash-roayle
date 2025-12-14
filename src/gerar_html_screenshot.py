#!/usr/bin/env python3
"""
Script para gerar HTML standalone para screenshot
Gera um HTML no estilo da imagem de exemplo com as informacoes do jogador
"""

import sqlite3
import os
import sys
from typing import Dict, List, Optional
from datetime import datetime

class ScreenshotHTMLGenerator:
    def __init__(self, db_path: str = "clash_royale.db"):
        self.db_path = db_path
    
    def get_card_filename(self, card_name: str) -> str:
        """Convert card name to filename"""
        card_mapping = {
            'Three Musketeers': '3M',
            'Hero Musketeer': 'Musk',
            'Musketeer': 'Musk',
            'Archer Queen': 'ArcherQueen',
            'Baby Dragon': 'BabyD',
            'Barbarian Barrel': 'BarbBarrel',
            'Barbarians': 'Barbs',
            'Battle Healer': 'BattleHealer',
            'Goblin Barrel': 'Barrel',
            'Bomb Tower': 'BombTower',
            'Boss Bandit': 'BossBandit',
            'Cannon Cart': 'CannonCart',
            'Dark Prince': 'DarkPrince',
            'Dart Goblin': 'DartGob',
            'Electro Giant': 'ElectroGiant',
            'Electro Spirit': 'ElectroSpirit',
            'Elixir Golem': 'ElixirGolem',
            'Executioner': 'Exe',
            'Fire Spirit': 'FireSpirit',
            'Flying Machine': 'FlyingMachine',
            'Goblin Gang': 'GobGang',
            'Goblin Giant': 'GobGiant',
            'Goblin Hut': 'GobHut',
            'Goblin Cage': 'GoblinCage',
            'Goblin Curse': 'GoblinCurse',
            'Goblin Demolisher': 'GoblinDemolisher',
            'Goblin Drill': 'GoblinDrill',
            'Goblin Machine': 'GoblinMachine',
            'Spear Goblins': 'Gobs',
            'Goblins': 'Gobs',
            'Golden Knight': 'GoldenKnight',
            'Giant Skeleton': 'GiantSkelly',
            'Heal Spirit': 'HealSpirit',
            'Hog Rider': 'Hog',
            'Minion Horde': 'Horde',
            'Ice Golem': 'IceGolem',
            'Ice Spirit': 'IceSpirit',
            'Ice Wizard': 'IceWiz',
            'Inferno Tower': 'Inferno',
            'Inferno Dragon': 'InfernoD',
            'Knight': 'Knight',
            'Lava Hound': 'Lava',
            'Lumberjack': 'Lumber',
            'Magic Archer': 'MagicArcher',
            'Mega Knight': 'MegaKnight',
            'Mighty Miner': 'MightyMiner',
            'Mini P.E.K.K.A': 'MP',
            'Minions': 'Minions',
            'Mortar': 'Mortar',
            'Mother Witch': 'MotherWitch',
            'Night Witch': 'NightWitch',
            'P.E.K.K.A': 'PEKKA',
            'Prince': 'Prince',
            'Princess': 'Princess',
            'Royal Giant': 'RG',
            'Royal Ghost': 'RoyalGhost',
            'Royal Hogs': 'RoyalHogs',
            'Royal Recruits': 'RoyalRecruits',
            'Skeleton Army': 'Skarmy',
            'Skeleton Dragons': 'SkeletonDragons',
            'Skeleton King': 'SkeletonKing',
            'Skeletons': 'Skellies',
            'Skeleton Barrel': 'SkellyBarrel',
            'Sparky': 'Sparky',
            'Tesla': 'Tesla',
            'The Log': 'Log',
            'Valkyrie': 'Valk',
            'Wall Breakers': 'WallBreakers',
            'Witch': 'Witch',
            'Wizard': 'Wiz',
            'X-Bow': 'XBow',
            'Zap': 'Zap',
            'Zappies': 'Zappies'
        }
        return card_mapping.get(card_name, card_name.replace(' ', '').replace('.', '').replace('-', ''))
    
    def get_card_image_path(self, card_name: str) -> str:
        """Get the path to card image (using relative paths from src/ directory)"""
        filename = self.get_card_filename(card_name)
        
        # Try hero cards first, then normal, then evolution
        # Use relative paths from src/ directory
        cards_base = "../cards" if os.path.exists("../cards") else "cards"
        
        if os.path.exists(f"{cards_base}/hero_cards/{filename}.png"):
            return f"../cards/hero_cards/{filename}.png"
        elif os.path.exists(f"{cards_base}/normal_cards/{filename}.png"):
            return f"../cards/normal_cards/{filename}.png"
        elif os.path.exists(f"{cards_base}/evolution_cards/{filename}.png"):
            return f"../cards/evolution_cards/{filename}.png"
        else:
            return f"https://via.placeholder.com/100x120/7B68EE/FFFFFF?text={card_name.replace(' ', '+')}"
    
    def get_player_stats(self) -> Optional[Dict]:
        """Get player statistics from database"""
        if not os.path.exists(self.db_path):
            return None
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get player info
        cursor.execute("SELECT * FROM players ORDER BY last_updated DESC LIMIT 1")
        player_row = cursor.fetchone()
        
        if not player_row:
            conn.close()
            return None
            
        # Get battle stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_battles,
                SUM(CASE WHEN result = 'victory' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'defeat' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result = 'draw' THEN 1 ELSE 0 END) as draws,
                SUM(COALESCE(trophy_change, 0)) as total_trophy_change
            FROM battles
        """)
        battle_stats = cursor.fetchone()
        
        conn.close()
        
        return {
            'player_tag': player_row[0],
            'name': player_row[1],
            'trophies': player_row[2],
            'best_trophies': player_row[3],
            'level': player_row[4],
            'clan_tag': player_row[5],
            'clan_name': player_row[6],
            'total_battles': battle_stats[0] or 0,
            'wins': battle_stats[1] or 0,
            'losses': battle_stats[2] or 0,
            'draws': battle_stats[3] or 0,
            'total_trophy_change': battle_stats[4] or 0
        }
    
    def get_top_deck(self, player_tag: str = None) -> Optional[Dict]:
        """Get most used deck (most battles) or deck with most wins"""
        if not os.path.exists(self.db_path):
            return None
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get player tag if not provided
        if not player_tag:
            cursor.execute("SELECT player_tag FROM players ORDER BY last_updated DESC LIMIT 1")
            player_row = cursor.fetchone()
            if player_row:
                player_tag = player_row[0]
        
        # Build query with optional player_tag filter
        query = """
            SELECT 
                deck_cards,
                COUNT(*) as total_battles,
                SUM(CASE WHEN result = 'victory' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'defeat' THEN 1 ELSE 0 END) as losses,
                SUM(COALESCE(trophy_change, 0)) as total_trophy_change,
                AVG(crowns) as avg_crowns
            FROM battles
            WHERE deck_cards IS NOT NULL AND deck_cards != ''
        """
        
        params = []
        if player_tag:
            query += " AND player_tag = ?"
            params.append(player_tag)
        
        query += """
            GROUP BY deck_cards
            HAVING total_battles >= 1
            ORDER BY 
                total_battles DESC,
                wins DESC
            LIMIT 1
        """
        
        cursor.execute(query, params)
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        deck_cards, total, wins, losses, trophies, avg_crowns = row
        win_rate = (wins / total * 100) if total > 0 else 0
        
        return {
            'deck_cards': deck_cards,
            'total_battles': total,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'trophy_change': trophies or 0,
            'avg_crowns': round(avg_crowns or 0, 1)
        }
    
    def generate_deck_cards_html(self, deck_cards: str) -> str:
        """Generate HTML for deck cards"""
        if not deck_cards:
            return ""
        
        cards = [c.strip() for c in deck_cards.split('|')]
        cards_html = ""
        
        for card in cards:
            img_path = self.get_card_image_path(card)
            cards_html += f'<div class="card-item"><img src="{img_path}" alt="{card}" class="card-img"></div>'
        
        return cards_html
    
    def generate_html(self) -> str:
        """Generate complete HTML document"""
        stats = self.get_player_stats()
        player_tag = stats.get('player_tag') if stats else None
        top_deck = self.get_top_deck(player_tag=player_tag)
        
        if not stats:
            return "<html><body><h1>Erro: Nenhum dado encontrado no banco de dados</h1></body></html>"
        
        win_rate = (stats['wins'] / max(stats['total_battles'], 1)) * 100
        
        deck_cards_html = ""
        if top_deck:
            deck_cards_html = self.generate_deck_cards_html(top_deck['deck_cards'])
        
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clash Royale Battle Analytics</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        
        .header h1 {{
            color: #2d3748;
            font-size: 2.5em;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
        }}
        
        .header-icon {{
            font-size: 1.2em;
        }}
        
        .player-info {{
            background: rgba(247, 250, 252, 0.8);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
        }}
        
        .player-info h2 {{
            color: #2d3748;
            font-size: 1.8em;
            margin-bottom: 10px;
        }}
        
        .player-info p {{
            color: #4a5568;
            font-size: 1.1em;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }}
        
        .stat-card h3 {{
            color: #4a5568;
            font-size: 0.9em;
            margin-bottom: 10px;
            font-weight: 600;
            white-space: normal;
            word-break: keep-all;
            line-height: 1.4;
        }}
        
        .stat-card h3 br {{
            display: block;
        }}
        
        .stat-card .value {{
            color: #4299e1;
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .stat-card small {{
            color: #718096;
            font-size: 0.85em;
        }}
        
        .top-decks-section {{
            margin-top: 40px;
        }}
        
        .top-decks-section h2 {{
            color: #2d3748;
            font-size: 1.8em;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .trophy-icon {{
            color: #d69e2e;
            font-size: 1.2em;
        }}
        
        .deck-card {{
            background: rgba(247, 250, 252, 0.8);
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 20px;
        }}
        
        .deck-header {{
            margin-bottom: 15px;
        }}
        
        .deck-header h3 {{
            color: #2d3748;
            font-size: 1.5em;
            margin-bottom: 10px;
        }}
        
        .deck-stats {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-bottom: 15px;
        }}
        
        .deck-stat {{
            background: white;
            padding: 8px 15px;
            border-radius: 5px;
            font-size: 0.9em;
            color: #4a5568;
        }}
        
        .deck-cards {{
            display: grid;
            grid-template-columns: repeat(8, 1fr);
            gap: 8px;
            margin-top: 20px;
        }}
        
        @media (max-width: 768px) {{
            .deck-cards {{
                grid-template-columns: repeat(4, 1fr);
            }}
        }}
        
        .card-item {{
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(255, 255, 255, 0.9);
            border-radius: 10px;
            padding: 10px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
        }}
        
        .card-img {{
            width: 100%;
            max-width: 100px;
            height: 120px;
            object-fit: contain;
            border-radius: 5px;
            display: block;
        }}
        
        @media (max-width: 768px) {{
            .deck-cards {{
                grid-template-columns: repeat(2, 1fr);
            }}
            
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>
                <span class="header-icon">⚔️</span>
                Clash Royale Battle Analytics
            </h1>
        </div>
        
        <div class="player-info">
            <h2>{stats['name']} ({stats['player_tag']})</h2>
            <p><strong>Clan:</strong> {stats['clan_name'] or 'Nenhum'} | <strong>Level:</strong> {stats['level']}</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Current Trophies</h3>
                <div class="value">{stats['trophies']:,}</div>
                <small>Best: {stats['best_trophies']:,}</small>
            </div>
            
            <div class="stat-card">
                <h3>Taxa de Vitória{(' -<br>' + stats['name']) if stats.get('name') else ''}</h3>
                <div class="value">{win_rate:.1f}%</div>
                <small>{stats['wins']}V / {stats['losses']}D</small>
            </div>
            
            <div class="stat-card">
                <h3>Total Battles</h3>
                <div class="value">{stats['total_battles']}</div>
                <small>{stats['draws']} draws</small>
            </div>
            
            <div class="stat-card">
                <h3>Trophy Change</h3>
                <div class="value" style="color: {'green' if stats['total_trophy_change'] >= 0 else 'red'}">{stats['total_trophy_change']:+d}</div>
                <small>Total from battles</small>
            </div>
        </div>
        
        {f'''
        <div class="top-decks-section">
            <h2>
                <span class="trophy-icon">🏆</span>
                Top Performing Decks
            </h2>
            
            <div class="deck-card">
                <div class="deck-header">
                    <h3>#1 - {top_deck['win_rate']:.1f}% Win Rate</h3>
                    <div class="deck-stats">
                        <span class="deck-stat">🏆 {top_deck['total_battles']} battles</span>
                        <span class="deck-stat">✅ {top_deck['wins']} wins</span>
                        <span class="deck-stat">❌ {top_deck['losses']} losses</span>
                        <span class="deck-stat" style="color: {'green' if top_deck['trophy_change'] >= 0 else 'red'}">📈 {top_deck['trophy_change']:+d} trophies</span>
                        <span class="deck-stat">👑 {top_deck['avg_crowns']:.1f} avg crowns</span>
                    </div>
                </div>
                <div class="deck-cards">
                    {deck_cards_html}
                </div>
            </div>
        </div>
        ''' if top_deck else '<div class="top-decks-section"><p>Nenhum deck encontrado</p></div>'}
    </div>
</body>
</html>"""

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Gera HTML standalone para screenshot')
    parser.add_argument('--db', type=str, default='clash_royale.db', help='Caminho do banco de dados')
    parser.add_argument('--output', type=str, default='screenshot.html', help='Arquivo de saida HTML')
    
    args = parser.parse_args()
    
    # Ajusta caminho do banco se estiver rodando de src/
    db_path = args.db
    if not os.path.exists(db_path) and os.path.exists(f"../{db_path}"):
        db_path = f"../{db_path}"
    
    generator = ScreenshotHTMLGenerator(db_path=db_path)
    html_content = generator.generate_html()
    
    output_path = args.output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"HTML gerado com sucesso: {output_path}")
    print(f"Abra o arquivo no navegador para visualizar e capturar o screenshot")

if __name__ == "__main__":
    main()

