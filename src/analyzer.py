#!/usr/bin/env python3
"""
Clash Royale Battle Analyzer for GitHub Pages
Lightweight version optimized for GitHub Actions
"""

import sqlite3
import requests
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import time

class ClashRoyaleAnalyzer:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.db_path = "clash_royale.db"
        self.base_url = "https://proxy.royaleapi.dev/v1"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Players table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                player_tag TEXT PRIMARY KEY,
                name TEXT,
                trophies INTEGER,
                best_trophies INTEGER,
                level INTEGER,
                clan_tag TEXT,
                clan_name TEXT,
                last_updated TEXT
            )
        """)
        
        # Battles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_tag TEXT,
                battle_time TEXT,
                battle_type TEXT,
                game_mode TEXT,
                is_ladder_tournament BOOLEAN,
                arena_id INTEGER,
                arena_name TEXT,
                result TEXT,
                crowns INTEGER,
                king_tower_hit_points INTEGER,
                princess_towers_hit_points TEXT,
                deck_cards TEXT,
                deck_card_levels TEXT,
                opponent_tag TEXT,
                opponent_name TEXT,
                opponent_trophies INTEGER,
                opponent_deck_cards TEXT,
                opponent_deck_card_levels TEXT,
                opponent_clan_tag TEXT,
                opponent_clan_name TEXT,
                player_level INTEGER,
                opponent_level INTEGER,
                battle_duration_seconds INTEGER,
                trophy_change INTEGER,
                FOREIGN KEY (player_tag) REFERENCES players (player_tag),
                UNIQUE(player_tag, battle_time, battle_type, game_mode)
            )
        """)
        
        # Add new columns to existing battles table (migration)
        new_columns = [
            ("deck_card_levels", "TEXT"),
            ("opponent_deck_card_levels", "TEXT"), 
            ("opponent_clan_tag", "TEXT"),
            ("opponent_clan_name", "TEXT"),
            ("player_level", "INTEGER"),
            ("opponent_level", "INTEGER"),
            ("battle_duration_seconds", "INTEGER")
        ]
        
        for column_name, column_type in new_columns:
            try:
                cursor.execute(f"ALTER TABLE battles ADD COLUMN {column_name} {column_type}")
            except sqlite3.OperationalError:
                # Column already exists
                pass
        
        # Clan members table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clan_members (
                player_tag TEXT PRIMARY KEY,
                name TEXT,
                role TEXT,
                level INTEGER,
                trophies INTEGER,
                donations INTEGER,
                donations_received INTEGER,
                clan_tag TEXT,
                clan_name TEXT,
                last_seen TEXT,
                last_updated TEXT
            )
        """)
        
        # Clan rankings history table for tracking progression
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clan_rankings_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_tag TEXT,
                name TEXT,
                clan_rank INTEGER,
                trophies INTEGER,
                donations INTEGER,
                donations_received INTEGER,
                trophy_change INTEGER,
                donation_change INTEGER,
                clan_tag TEXT,
                clan_name TEXT,
                recorded_at TEXT,
                FOREIGN KEY (player_tag) REFERENCES players (player_tag),
                UNIQUE(player_tag, recorded_at)
            )
        """)
        
        # Clan member deck changes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clan_member_decks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_tag TEXT,
                name TEXT,
                deck_cards TEXT,
                favorite_card TEXT,
                arena_id INTEGER,
                arena_name TEXT,
                league_id INTEGER,
                league_name TEXT,
                exp_level INTEGER,
                trophies INTEGER,
                best_trophies INTEGER,
                first_seen TEXT,
                last_seen TEXT,
                clan_tag TEXT,
                clan_name TEXT,
                FOREIGN KEY (player_tag) REFERENCES players (player_tag)
            )
        """)
        
        # Deck performance view
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS deck_performance AS
            SELECT 
                deck_cards,
                COUNT(*) as total_battles,
                SUM(CASE WHEN result = 'victory' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'defeat' THEN 1 ELSE 0 END) as losses,
                ROUND(AVG(CASE WHEN result = 'victory' THEN 1.0 ELSE 0.0 END) * 100, 2) as win_rate,
                SUM(COALESCE(trophy_change, 0)) as total_trophy_change,
                ROUND(AVG(COALESCE(trophy_change, 0)), 2) as avg_trophy_change,
                ROUND(AVG(crowns), 2) as avg_crowns
            FROM battles 
            WHERE deck_cards IS NOT NULL
            GROUP BY deck_cards
            ORDER BY win_rate DESC, total_battles DESC
        """)
        
        conn.commit()
        conn.close()
    
    def get_player_info(self, player_tag: str) -> Optional[Dict]:
        """Fetch player information from API"""
        clean_tag = player_tag.replace('#', '')
        url = f"{self.base_url}/players/%23{clean_tag}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching player info: {e}")
            return None
    
    def get_battle_log(self, player_tag: str) -> Optional[List[Dict]]:
        """Fetch player's battle log from API"""
        clean_tag = player_tag.replace('#', '')
        url = f"{self.base_url}/players/%23{clean_tag}/battlelog"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching battle log: {e}")
            return None
    
    def get_clan_info(self, clan_tag: str) -> Optional[Dict]:
        """Fetch clan information from API"""
        clean_tag = clan_tag.replace('#', '')
        url = f"{self.base_url}/clans/%23{clean_tag}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching clan info: {e}")
            return None
    
    def save_player_info(self, player_data: Dict):
        """Save player information to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        clan_info = player_data.get('clan', {})
        
        cursor.execute("""
            INSERT OR REPLACE INTO players 
            (player_tag, name, trophies, best_trophies, level, clan_tag, clan_name, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            player_data['tag'],
            player_data['name'],
            player_data.get('trophies', 0),
            player_data.get('bestTrophies', 0),
            player_data.get('expLevel', 0),
            clan_info.get('tag'),
            clan_info.get('name'),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def save_clan_members(self, clan_data: Dict):
        """Save clan member information to database and remove members who left"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        clan_tag = clan_data['tag']
        clan_name = clan_data['name']
        
        # Get current active member tags from API
        current_member_tags = {member['tag'] for member in clan_data.get('memberList', [])}
        
        # Remove members who are no longer in the clan
        if current_member_tags:
            placeholders = ','.join(['?'] * len(current_member_tags))
            cursor.execute(f"""
                DELETE FROM clan_members 
                WHERE clan_tag = ? AND player_tag NOT IN ({placeholders})
            """, [clan_tag] + list(current_member_tags))
        else:
            # If no members in API response, remove all members from this clan
            cursor.execute("""
                DELETE FROM clan_members WHERE clan_tag = ?
            """, (clan_tag,))
        
        # Insert or update current members
        for member in clan_data.get('memberList', []):
            cursor.execute("""
                INSERT OR REPLACE INTO clan_members 
                (player_tag, name, role, level, trophies, donations, donations_received, 
                 clan_tag, clan_name, last_seen, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                member['tag'],
                member['name'],
                member['role'],
                member.get('expLevel', 0),
                member.get('trophies', 0),
                member.get('donations', 0),
                member.get('donationsReceived', 0),
                clan_tag,
                clan_name,
                member.get('lastSeen'),
                datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
    
    def save_clan_rankings_history(self, clan_data: Dict):
        """Save clan rankings progression to track member performance over time"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        clan_tag = clan_data['tag']
        clan_name = clan_data['name']
        current_time = datetime.now().isoformat()
        
        # Sort members by trophies to get rankings
        members = clan_data.get('memberList', [])
        members_sorted = sorted(members, key=lambda x: x.get('trophies', 0), reverse=True)
        
        for rank, member in enumerate(members_sorted, 1):
            player_tag = member['tag']
            
            # Get previous data for calculating changes
            cursor.execute("""
                SELECT trophies, donations 
                FROM clan_rankings_history 
                WHERE player_tag = ? 
                ORDER BY recorded_at DESC 
                LIMIT 1
            """, (player_tag,))
            
            previous_data = cursor.fetchone()
            current_trophies = member.get('trophies', 0)
            current_donations = member.get('donations', 0)
            
            trophy_change = 0
            donation_change = 0
            
            if previous_data:
                trophy_change = current_trophies - (previous_data[0] or 0)
                donation_change = current_donations - (previous_data[1] or 0)
            
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO clan_rankings_history 
                    (player_tag, name, clan_rank, trophies, donations, donations_received,
                     trophy_change, donation_change, clan_tag, clan_name, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_tag,
                    member['name'],
                    rank,
                    current_trophies,
                    current_donations,
                    member.get('donationsReceived', 0),
                    trophy_change,
                    donation_change,
                    clan_tag,
                    clan_name,
                    current_time
                ))
            except sqlite3.Error as e:
                print(f"Error inserting clan ranking for {member['name']}: {e}")
                continue
        
        conn.commit()
        conn.close()
    
    def save_clan_member_deck_if_changed(self, player_data: Dict, clan_tag: str, clan_name: str):
        """Save clan member deck only if it has changed from the last recorded deck"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        player_tag = player_data['tag']
        current_time = datetime.now().isoformat()
        
        # Format current deck
        current_deck = self.format_deck(player_data.get('currentDeck', []))
        favorite_card = player_data.get('currentFavouriteCard', {}).get('name', '')
        
        # Get arena and league info
        arena_info = player_data.get('arena', {})
        league_info = player_data.get('league', {})
        
        # Check if this deck is different from the last recorded deck
        cursor.execute("""
            SELECT deck_cards, favorite_card 
            FROM clan_member_decks 
            WHERE player_tag = ? 
            ORDER BY id DESC 
            LIMIT 1
        """, (player_tag,))
        
        last_record = cursor.fetchone()
        
        # Save only if deck changed or no previous record (ignore favorite card changes)
        should_save = (
            not last_record or 
            last_record[0] != current_deck
        )
        
        if should_save:
            try:
                cursor.execute("""
                    INSERT INTO clan_member_decks 
                    (player_tag, name, deck_cards, favorite_card, arena_id, arena_name,
                     league_id, league_name, exp_level, trophies, best_trophies,
                     first_seen, last_seen, clan_tag, clan_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_tag,
                    player_data['name'],
                    current_deck,
                    favorite_card,
                    arena_info.get('id'),
                    arena_info.get('name'),
                    league_info.get('id') if league_info else None,
                    league_info.get('name') if league_info else None,
                    player_data.get('expLevel', 0),
                    player_data.get('trophies', 0),
                    player_data.get('bestTrophies', 0),
                    current_time,
                    current_time,
                    clan_tag,
                    clan_name
                ))
                print(f"  → Saved new deck for {player_data['name']}")
            except sqlite3.Error as e:
                print(f"Error saving deck for {player_data['name']}: {e}")
        else:
            # Update last_seen and favorite_card for existing deck
            cursor.execute("""
                UPDATE clan_member_decks 
                SET last_seen = ?, favorite_card = ? 
                WHERE player_tag = ? 
                  AND id = (SELECT id FROM clan_member_decks WHERE player_tag = ? ORDER BY id DESC LIMIT 1)
            """, (current_time, favorite_card, player_tag, player_tag))
        
        conn.commit()
        conn.close()
    
    def fetch_clan_member_details(self, clan_info: Dict):
        """Fetch detailed player information for each clan member"""
        clan_tag = clan_info['tag']
        clan_name = clan_info['name']
        members = clan_info.get('memberList', [])
        
        print(f"Fetching detailed data for {len(members)} clan members...")
        
        # Get main player tag to identify which member is the main player
        cursor = sqlite3.connect(self.db_path).cursor()
        cursor.execute("SELECT player_tag FROM players ORDER BY last_updated DESC LIMIT 1")
        main_player_row = cursor.fetchone()
        main_player_tag = main_player_row[0] if main_player_row else None
        cursor.connection.close()
        
        for i, member in enumerate(members, 1):
            member_tag = member['tag']
            member_trophies = member.get('trophies', 0)
            print(f"  {i}/{len(members)}: {member['name']} ({member_tag})")
            
            # Get detailed player info
            player_data = self.get_player_info(member_tag)
            if player_data:
                self.save_clan_member_deck_if_changed(player_data, clan_tag, clan_name)
                
                # For members with >= 10K trophies (and not the main player), fetch their battles
                if member_trophies >= 10000 and member_tag != main_player_tag:
                    print(f"    Fetching battles for {member['name']} (>= 10K trophies)...")
                    battles = self.get_battle_log(member_tag)
                    if battles:
                        self.save_battles(member_tag, battles)
                        print(f"    Saved {len(battles)} battles")
                    # Extra rate limiting for battle logs
                    time.sleep(1)
            
            # Rate limiting - be nice to the API
            time.sleep(0.5)
    
    def format_deck(self, cards: List[Dict]) -> str:
        """Format deck cards as a sorted string for consistent comparison"""
        card_names = sorted([card['name'] for card in cards])
        return ' | '.join(card_names)
    
    def format_deck_with_levels(self, cards: List[Dict]) -> str:
        """Format deck cards with levels as JSON string for detailed analysis"""
        card_data = []
        for card in cards:
            card_info = {
                'name': card['name'],
                'level': card.get('level', 1),
                'max_level': card.get('maxLevel', 15),
                'evolved': card.get('evolved', False),
                'id': card.get('id')
            }
            card_data.append(card_info)
        
        # Sort by card name for consistency
        card_data.sort(key=lambda x: x['name'])
        return json.dumps(card_data)
    
    def calculate_battle_duration(self, battle_time: str, battle_data: Dict) -> Optional[int]:
        """Calculate battle duration in seconds from battle data"""
        # The API might provide duration directly, or we might need to calculate it
        # For now, return None as duration isn't always available in the API
        duration = battle_data.get('duration')
        if duration:
            return int(duration)
        return None
    
    def save_battles(self, player_tag: str, battles: List[Dict]):
        """Save battle log to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for battle in battles:
            # Get player team (should be the only team in the team array)
            teams = battle.get('team', [])
            player_team = None
            
            # Find the player's team
            for team in teams:
                if team.get('tag') == player_tag:
                    player_team = team
                    break
            
            if not player_team:
                continue
            
            # Get opponent data from the 'opponent' field (it's an array)
            opponents = battle.get('opponent', [])
            opponent_team = opponents[0] if opponents else None
            
            # Format deck cards and card levels
            deck_cards = self.format_deck(player_team.get('cards', []))
            deck_card_levels = self.format_deck_with_levels(player_team.get('cards', []))
            opponent_deck_cards = self.format_deck(opponent_team.get('cards', [])) if opponent_team else None
            opponent_deck_card_levels = self.format_deck_with_levels(opponent_team.get('cards', [])) if opponent_team else None
            
            # Extract player and opponent levels
            player_level = player_team.get('expLevel')
            opponent_level = opponent_team.get('expLevel') if opponent_team else None
            
            # Extract opponent clan info
            opponent_clan_tag = opponent_team.get('clan', {}).get('tag') if opponent_team else None
            opponent_clan_name = opponent_team.get('clan', {}).get('name') if opponent_team else None
            
            # Calculate battle duration (if available)
            battle_duration = self.calculate_battle_duration(battle['battleTime'], battle)
            
            # Determine result
            player_crowns = player_team.get('crowns', 0)
            opponent_crowns = opponent_team.get('crowns', 0) if opponent_team else 0
            
            if player_crowns > opponent_crowns:
                result = 'victory'
            elif player_crowns < opponent_crowns:
                result = 'defeat'
            else:
                result = 'draw'
            
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO battles 
                    (player_tag, battle_time, battle_type, game_mode, is_ladder_tournament,
                     arena_id, arena_name, result, crowns, king_tower_hit_points,
                     princess_towers_hit_points, deck_cards, deck_card_levels, 
                     opponent_tag, opponent_name, opponent_trophies, opponent_deck_cards, 
                     opponent_deck_card_levels, opponent_clan_tag, opponent_clan_name,
                     player_level, opponent_level, battle_duration_seconds, trophy_change)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_tag,
                    battle['battleTime'],
                    battle.get('type'),
                    battle.get('gameMode', {}).get('name'),
                    battle.get('isLadderTournament', False),
                    battle.get('arena', {}).get('id'),
                    battle.get('arena', {}).get('name'),
                    result,
                    player_crowns,
                    player_team.get('kingTowerHitPoints'),
                    json.dumps(player_team.get('princessTowersHitPoints', [])),
                    deck_cards,
                    deck_card_levels,
                    opponent_team.get('tag') if opponent_team else None,
                    opponent_team.get('name') if opponent_team else None,
                    opponent_team.get('startingTrophies') if opponent_team else None,
                    opponent_deck_cards,
                    opponent_deck_card_levels,
                    opponent_clan_tag,
                    opponent_clan_name,
                    player_level,
                    opponent_level,
                    battle_duration,
                    player_team.get('trophyChange')
                ))
            except sqlite3.Error as e:
                print(f"Error inserting battle: {e}")
                continue
        
        conn.commit()
        conn.close()
    
    def update_player_data(self, player_tag: str):
        """Fetch and save latest player data and battles"""
        print(f"Updating data for player {player_tag}...")
        
        # Get player info
        player_info = self.get_player_info(player_tag)
        if player_info:
            self.save_player_info(player_info)
            print(f"Updated player info for {player_info['name']}")
            
            # Update clan data if player is in a clan
            if 'clan' in player_info:
                clan_tag = player_info['clan']['tag']
                print(f"Updating clan data for {player_info['clan']['name']}...")
                clan_info = self.get_clan_info(clan_tag)
                if clan_info:
                    self.save_clan_members(clan_info)
                    self.save_clan_rankings_history(clan_info)
                    self.fetch_clan_member_details(clan_info)
                    print(f"Updated clan data with {len(clan_info.get('memberList', []))} members, rankings, and deck tracking")
        
        # Get battle log
        battles = self.get_battle_log(player_tag)
        if battles:
            self.save_battles(player_tag, battles)
            print(f"Updated {len(battles)} battles")
        
        # Rate limiting
        time.sleep(1)

def main():
    """Main entry point for GitHub Actions"""
    # Get credentials from environment variables
    API_TOKEN = os.getenv("CR_API_TOKEN")
    PLAYER_TAG = os.getenv("CR_PLAYER_TAG")
    
    if not API_TOKEN:
        print("Error: CR_API_TOKEN environment variable not set")
        exit(1)
    
    if not PLAYER_TAG:
        print("Error: CR_PLAYER_TAG environment variable not set")
        exit(1)
    
    print(f"Starting analysis for player: {PLAYER_TAG}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Initialize analyzer and update data
    analyzer = ClashRoyaleAnalyzer(API_TOKEN)
    analyzer.update_player_data(PLAYER_TAG)
    
    print("Data collection completed successfully!")

if __name__ == "__main__":
    main()