#!/usr/bin/env python3
"""
Individual Member HTML Generator for GitHub Pages
Generates detailed member pages with deck change tracking
"""

import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional
from html_generator import GitHubPagesHTMLGenerator

logger = logging.getLogger(__name__)


class MemberPageGenerator(GitHubPagesHTMLGenerator):
    def __init__(self, output_path: str = './'):
        super().__init__()
        self.output_path = output_path
    
    def get_member_deck_history(self, player_tag: str) -> List[Dict]:
        """Get complete deck change history for a member, consolidating consecutive identical decks"""
        if not hasattr(self.csv_manager, 'conn') or self.csv_manager.conn is None:
            # Em modo 100% CSV, o historico de decks para a linha do tempo e carregado
            # via arquivos players.csv ou clan_members.csv se disponivel.
            # Por enquanto, retornamos vazio para evitar quebra do build.
            return []
            
        conn = self.csv_manager.conn
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clan_member_decks'")
        if not cursor.fetchone():
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
        if not hasattr(self.csv_manager, 'conn') or self.csv_manager.conn is None:
            # Modo Fallback CSV: Procura no clan_members_cache
            for m in self.clan_members_cache:
                if m.get('player_tag') == player_tag:
                    return {
                        'player_tag': player_tag,
                        'name': m.get('name', 'Desconhecido'),
                        'role': m.get('role', 'member'),
                        'trophies': int(m.get('trophies', 0) or 0),
                        'donations': int(m.get('donations', 0) or 0),
                        'donations_received': int(m.get('donations_received', 0) or 0),
                        'last_seen': m.get('last_seen', '')
                    }
            return None
            
        conn = self.csv_manager.conn
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name, role, trophies, donations, donations_received, last_seen
            FROM clan_members 
            WHERE player_tag = ?
        """, (player_tag,))

        row = cursor.fetchone()
        if not row:
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
        """Gerar página de erro quando os dados do membro não estão disponíveis"""
        return f"""
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Perfil do Membro - Sem Dados</title>
    <style>
        {self.get_base_css_styles()}
        .error-container {{
            max-width: 600px;
            margin: 100px auto;
            text-align: center;
            padding: 60px;
        }}
        .error-icon {{
            font-size: 5em;
            margin-bottom: 20px;
            display: block;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="glass-panel error-container">
            <span class="error-icon">👤</span>
            <h1 class="clash-font">Perfil não encontrado</h1>
            <p style="color: #94a3b8; margin: 20px 0;">Os dados deste membro estão sendo processados ou o jogador não foi encontrado no clã atualmente.</p>
            <div style="margin-top: 30px;">
                <a href="clan.html" class="back-link" style="display: inline-block; background: var(--primary); color: white; padding: 12px 25px; border-radius: 50px; text-decoration: none; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;">← Voltar ao Clã</a>
            </div>
        </div>
    </div>
</body>
</html>
        """
    
    def generate_deck_timeline_html(self, deck_history: List[Dict]) -> str:
        """Gerar linha do tempo HTML das mudanças de deck"""
        if not deck_history:
            return '<div class="glass-panel" style="padding: 30px; text-align: center; color: #94a3b8;">Nenhum histórico de deck disponível ainda.</div>'
        
        timeline_html = '<div class="deck-timeline">'
        
        for i, deck in enumerate(deck_history):
            is_current = i == 0  # Primeiro item é o mais recente
            timeline_class = "timeline-current" if is_current else "timeline-past"
            status_badge = '<span class="status-badge current">Atual</span>' if is_current else '<span class="status-badge past">Anterior</span>'
            
            deck_cards_html = self.generate_deck_cards_html(deck['deck_cards'], show_names=False)
            
            # Divisão resiliente de cartas usando pipe ou vírgula
            if ' | ' in deck['deck_cards']:
                cards_list = deck['deck_cards'].split(' | ')
            elif '|' in deck['deck_cards']:
                cards_list = deck['deck_cards'].split('|')
            else:
                cards_list = deck['deck_cards'].split(',')
                
            copy_link = self.get_copy_deck_link(cards_list)

            
            timeline_html += f'''
                <div class="timeline-item {timeline_class} glass-panel">
                    <div class="timeline-marker">
                        <div class="timeline-date">{self.format_date(deck['first_seen'])}</div>
                        <div class="timeline-duration">{deck['duration']}</div>
                    </div>
                    <div class="timeline-content">
                        <div class="deck-header-row">
                            <div class="deck-title-group">
                                <h3 class="clash-font">{status_badge} Histórico de Deck</h3>
                                <div class="deck-meta">
                                    <span class="meta-item">🏆 {deck['trophies']:,}</span>
                                    <span class="meta-item">🏟️ {deck['arena_name'] or 'Desconhecida'}</span>
                                    <span class="meta-item">⭐ {deck['favorite_card'] or 'Nenhuma'}</span>
                                </div>
                            </div>
                            <button type="button" onclick="copyDeckLink(event, this, '{copy_link}')" class="cr-copy-btn-v2" style="background: transparent; border: none; padding: 0; cursor: pointer; transition: transform 0.2s; display: inline-flex; align-items: center; justify-content: center;" title="Copiar Deck"><img src="https://media.ffycdn.net/eu/supercell/jsmnnT9Z8mF79QiwDcsW.png?width=2400" alt="Copiar Deck" style="height: 28px; vertical-align: middle;"></button>
                        </div>
                        <div class="timeline-deck-grid">
                            {deck_cards_html}
                        </div>
                    </div>
                </div>
            '''
        
        timeline_html += '</div>'
        return timeline_html
    
    def generate_member_full_html(self, member_info: Dict, deck_history: List[Dict]) -> str:
        """Gerar o HTML completo da página do membro"""
        
        role_class = {
            'leader': 'leader',
            'coLeader': 'co-leader', 
            'elder': 'elder',
            'member': 'member'
        }.get(member_info['role'], 'member')
        
        # Tradução de cargos
        role_display = {
            'leader': 'Líder',
            'coLeader': 'Co-Líder',
            'elder': 'Veterano',
            'member': 'Membro'
        }.get(member_info['role'], 'Membro')
        
        deck_timeline_html = self.generate_deck_timeline_html(deck_history)
        
        css_styles = self.get_base_css_styles() + """
        /* Member Page Specific Styles - Premium v2 */
        .member-profile-header {
            padding: 60px 40px;
            margin-bottom: 40px;
            text-align: center;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 25px;
        }

        .member-avatar {
            font-size: 4em;
            background: rgba(255,255,255,0.05);
            width: 100px;
            height: 100px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            border: 2px solid var(--primary);
            box-shadow: 0 0 20px var(--primary-glow);
        }

        .member-name-tag {
            font-size: 3.5em;
            margin-bottom: 5px;
            background: linear-gradient(135deg, #fff 0%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .role-badge {
            padding: 8px 20px;
            border-radius: 50px;
            font-weight: 800;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }

        .role-leader { background: linear-gradient(135deg, #f6e05e 0%, #d69e2e 100%); color: #000; }
        .role-co-leader { background: linear-gradient(135deg, #63b3ed 0%, #3182ce 100%); color: #fff; }
        .role-elder { background: linear-gradient(135deg, #68d391 0%, #38a169 100%); color: #fff; }
        .role-member { background: linear-gradient(135deg, #a0aec0 0%, #718096 100%); color: #fff; }

        .member-stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 25px;
            width: 100%;
            margin-top: 20px;
        }

        .deck-timeline {
            position: relative;
            padding-left: 20px;
            margin-top: 40px;
        }

        .timeline-item {
            margin-bottom: 40px;
            padding: 30px;
            position: relative;
            transition: all 0.3s ease;
        }

        .timeline-item:hover {
            border-color: var(--primary);
            transform: translateX(10px);
        }

        .timeline-marker {
            position: absolute;
            left: -100px;
            top: 30px;
            width: 80px;
            text-align: right;
        }

        .timeline-date {
            font-size: 0.85em;
            color: var(--primary);
            font-weight: 800;
        }

        .timeline-duration {
            font-size: 0.75em;
            color: #64748b;
        }

        .deck-header-row {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 25px;
            flex-wrap: wrap;
            gap: 20px;
        }

        .deck-meta {
            display: flex;
            gap: 15px;
            margin-top: 10px;
            flex-wrap: wrap;
        }

        .meta-item {
            font-size: 0.85em;
            background: rgba(255,255,255,0.05);
            padding: 5px 12px;
            border-radius: 8px;
            color: #cbd5e0;
        }

        .status-badge {
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 0.7em;
            font-weight: 800;
            text-transform: uppercase;
            margin-right: 10px;
            vertical-align: middle;
        }

        .status-badge.current { background: var(--success); color: #fff; }
        .status-badge.past { background: rgba(255,255,255,0.1); color: #94a3b8; }

        .copy-btn {
            background: transparent;
            border: none;
            padding: 4px 8px;
            cursor: pointer;
            transition: transform 0.2s ease;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }

        .copy-btn:hover {
            transform: scale(1.1);
        }

        .timeline-deck-grid {
            display: grid;
            grid-template-columns: repeat(8, 1fr);
            gap: 10px;
        }

        .back-btn-container {
            margin-bottom: 30px;
        }

        .back-btn {
            color: #94a3b8;
            text-decoration: none;
            font-weight: 600;
            transition: color 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .back-btn:hover {
            color: var(--primary);
        }

        @media (max-width: 900px) {
            .timeline-marker {
                position: static;
                width: 100%;
                text-align: left;
                margin-bottom: 15px;
            }
            .timeline-deck-grid {
                grid-template-columns: repeat(4, 1fr);
            }
            .deck-header-row {
                flex-direction: column;
            }
        }
        """
        
        return f"""
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Perfil de Membro - {member_info['name']}</title>
    <link rel="icon" type="image/x-icon" href="favicon.ico">
    <style>{css_styles}</style>
</head>
<body>
    <div class="container">
        <div class="back-btn-container">
            <a href="clan.html" class="back-btn">← Voltar para Análise do Clã</a>
        </div>
        
        <header class="glass-panel member-profile-header">
            <div class="member-avatar">👤</div>
            <div class="member-info-group">
                <h1 class="clash-font member-name-tag">{member_info['name']}</h1>
                <span class="role-badge role-{role_class}">{role_display}</span>
            </div>
            
            <div class="member-stats-grid">
                <div class="stat-card">
                    <h3>Troféus Atuais</h3>
                    <div class="value">🏆 {member_info['trophies']:,}</div>
                </div>
                <div class="stat-card">
                    <h3>Doações Dadas</h3>
                    <div class="value">↑ {member_info['donations']}</div>
                </div>
                <div class="stat-card">
                    <h3>Doações Recebidas</h3>
                    <div class="value">↓ {member_info['donations_received']}</div>
                </div>
                <div class="stat-card">
                    <h3>Mudanças de Deck</h3>
                    <div class="value">🔄 {len(deck_history)}</div>
                </div>
            </div>
        </header>

        <section class="section">
            <h2 class="clash-font">🃏 Linha do Tempo de Decks</h2>
            <p style="color: #94a3b8; margin-bottom: 30px; font-style: italic;">
                Histórico completo de trocas de decks e evolução de cartas favoritas.
            </p>
            {deck_timeline_html}
        </section>

        <footer style="margin-top: 60px; text-align: center; color: #64748b; padding-bottom: 40px;">
            <p>Perfil gerado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
            <p>Visto por último: {self.format_time_ago(member_info['last_seen'])}</p>
            <div style="margin-top: 20px;">
                <a href="clan.html" class="back-btn">← Voltar para Análise do Clã</a>
            </div>
        </footer>
    </div>
</body>
</html>
        """

def main():
    """Generate member pages for all clan members"""
    # Get the repository root directory (two levels up from generators)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(script_dir))
    
    generator = MemberPageGenerator(output_path=root_dir)
    generated_pages = []
    
    # Tenta obter membros via SQL ou fallback para Cache de CSV
    if hasattr(generator.csv_manager, 'conn') and generator.csv_manager.conn:
        conn = generator.csv_manager.conn
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT player_tag, name FROM clan_members")
        members = cursor.fetchall()
    else:
        # Modo Fallback: Usa o cache ja carregado do clan_members.csv no HTMLGenerator
        logger.info("Modo SQL indisponivel. Usando cache de membros do CSV.")
        members = [(m['player_tag'], m['name']) for m in generator.clan_members_cache]
    
    if not members:
        print("No clan members found")
        return []
    
    # Save in root directory
    for player_tag, name in members:
        html_content = generator.generate_member_page(player_tag)
        safe_name = generator.safe_filename(name)
        filename = f"member_{safe_name}.html"
        filepath = os.path.join(root_dir, 'docs', filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        generated_pages.append((name, filename))
        print(f"Generated: {filepath}")
    
    print(f"Generated {len(generated_pages)} member pages")
    return generated_pages

if __name__ == "__main__":
    main()