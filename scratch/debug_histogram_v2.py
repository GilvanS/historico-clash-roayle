
import sqlite3
import os
import sys
from datetime import datetime

# Add src to path
sys.path.append(os.path.abspath('src'))
from html_generator import GitHubPagesHTMLGenerator

def debug_histogram():
    generator = GitHubPagesHTMLGenerator()
    # stats = generator.get_player_stats()
    # player_tag = stats.get('player_tag')
    player_tag = '#2QR292P'
    print(f"Using player_tag: {player_tag}")
    
    daily_stats = generator.get_daily_battle_stats(30, player_tag=player_tag)
    
    print(f"Daily stats returned {len(daily_stats)} rows.")
    
    days_with_battles = [d for d in daily_stats if d['total_battles'] > 0]
    print(f"Days with battles: {len(days_with_battles)}")
    
    for d in days_with_battles:
        print(f"  {d['date']}: {d['wins']}W / {d['losses']}L / {d['draws']}D (Total: {d['total_battles']})")
    
    # Check max_battles calculation used in generate_daily_histogram_html
    if daily_stats:
        max_battles = max((day['total_battles'] for day in daily_stats), default=1)
        print(f"Max battles for scaling: {max_battles}")
        
        # Test HTML generation for one bar
        if days_with_battles:
            day = days_with_battles[0]
            total = day['total_battles']
            wins = day['wins']
            scale_factor = (total / max_battles) * 180
            win_height = max((wins / total) * scale_factor, 1 if wins > 0 else 0)
            print(f"Sample bar height (win): {win_height}px")

if __name__ == "__main__":
    debug_histogram()
