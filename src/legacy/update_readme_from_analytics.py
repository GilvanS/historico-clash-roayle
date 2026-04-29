#!/usr/bin/env python3
"""
Script para atualizar o README com estatisticas de decks do banco clash_royale.db
"""

import sqlite3
import os
import sys
from csv_database_manager import CSVDatabaseManager
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone

class ReadmeAnalyticsUpdater:
    def __init__(self, db_path: str = None, readme_path: str = "README.md"):
        # Inicializa o gerenciador de CSV e carrega os dados para a memoria
        self.csv_manager = CSVDatabaseManager()
        self.csv_manager.load_all_csvs()
        
        # Define o path como a URI de memoria compartilhada
        self.db_path = self.csv_manager.db_path
        self.readme_path = readme_path
    
    def get_deck_stats(self, player_tag: str) -> Dict:
        """Analisa estatisticas de decks do banco de dados em memoria"""
        conn = sqlite3.connect(self.db_path, uri=True)
        cursor = conn.cursor()
        
        # Deck atual (mais recente)
        cursor.execute("""
            SELECT deck_cards, result, battle_time
            FROM battles
            WHERE player_tag = ? AND deck_cards IS NOT NULL AND deck_cards != ''
            ORDER BY battle_time DESC
            LIMIT 1
        """, (player_tag,))
        
        deck_atual_row = cursor.fetchone()
        deck_atual = None
        if deck_atual_row:
            deck_atual = {
                'deck': deck_atual_row[0],
                'ultimo_resultado': deck_atual_row[1],
                'battle_time': deck_atual_row[2]
            }
        
        # Estatisticas por deck
        cursor.execute("""
            SELECT 
                deck_cards,
                COUNT(*) as total_batalhas,
                SUM(CASE WHEN result = 'victory' THEN 1 ELSE 0 END) as vitorias,
                SUM(CASE WHEN result = 'defeat' THEN 1 ELSE 0 END) as derrotas,
                SUM(COALESCE(trophy_change, 0)) as trofes_total
            FROM battles
            WHERE player_tag = ? AND deck_cards IS NOT NULL AND deck_cards != ''
            GROUP BY deck_cards
            HAVING total_batalhas >= 1
            ORDER BY 
                (CAST(vitorias AS FLOAT) / CAST(total_batalhas AS FLOAT)) DESC,
                total_batalhas DESC
        """, (player_tag,))
        
        decks_stats = []
        for row in cursor.fetchall():
            deck, total, vitorias, derrotas, trofes_total = row
            win_rate = (vitorias / total * 100) if total > 0 else 0
            
            decks_stats.append({
                'deck': deck,
                'total_batalhas': total,
                'vitorias': vitorias,
                'derrotas': derrotas,
                'win_rate': win_rate,
                'trofes_total': trofes_total or 0
            })
        
        # Estatisticas gerais
        cursor.execute("""
            SELECT 
                COUNT(*) as total_batalhas,
                SUM(CASE WHEN result = 'victory' THEN 1 ELSE 0 END) as vitorias,
                SUM(CASE WHEN result = 'defeat' THEN 1 ELSE 0 END) as derrotas,
                SUM(COALESCE(trophy_change, 0)) as trofes_total
            FROM battles
            WHERE player_tag = ?
        """, (player_tag,))
        
        stats_gerais_row = cursor.fetchone()
        stats_gerais = None
        if stats_gerais_row:
            total, vitorias, derrotas, trofes_total = stats_gerais_row
            win_rate_geral = (vitorias / total * 100) if total > 0 else 0
            stats_gerais = {
                'total_batalhas': total or 0,
                'vitorias': vitorias or 0,
                'derrotas': derrotas or 0,
                'win_rate': win_rate_geral,
                'trofes_total': trofes_total or 0
            }
        
        # Deck com melhor win rate (minimo 3 batalhas)
        deck_melhor = None
        for deck_stat in decks_stats:
            if deck_stat['total_batalhas'] >= 3:
                deck_melhor = deck_stat
                break
        
        # Se nao tem deck com 3+ batalhas, pega o melhor disponivel
        if not deck_melhor and decks_stats:
            deck_melhor = decks_stats[0]
        
        conn.close()
        
        return {
            'deck_atual': deck_atual,
            'deck_melhor': deck_melhor,
            'decks_stats': decks_stats,
            'stats_gerais': stats_gerais
        }
    
    def format_deck_for_readme(self, deck_string: str) -> str:
        """Formata deck para exibicao no README"""
        if not deck_string:
            return "N/A"
        # O formato do deck_cards no clash_royale.db é "Card1 | Card2 | Card3 | ..."
        cards = deck_string.split(' | ')
        return ", ".join(cards)
    
    def update_readme(self, player_tag: str):
        """Atualiza o README com as estatisticas"""
        stats = self.get_deck_stats(player_tag)
        
        if not stats or not stats['stats_gerais']:
            print("Nenhuma estatistica encontrada no banco de dados")
            return
        
        if not os.path.exists(self.readme_path):
            print(f"README nao encontrado: {self.readme_path}")
            return
        
        # Le o README atual
        with open(self.readme_path, 'r', encoding='utf-8') as f:
            readme_content = f.read()
        
        # Procura pela secao de estatisticas ou cria uma nova
        stats_section_start = "## 📊 Estatísticas Atuais"
        stats_section_end = "## "
        
        # Se a secao ja existe, substitui
        if stats_section_start in readme_content:
            # Encontra o inicio da secao
            start_idx = readme_content.find(stats_section_start)
            # Encontra o proximo ## apos a secao
            next_section_idx = readme_content.find(stats_section_end, start_idx + len(stats_section_start))
            
            if next_section_idx != -1:
                # Remove a secao antiga
                readme_content = readme_content[:start_idx] + readme_content[next_section_idx:]
        
        # Gera a nova secao de estatisticas
        stats_section = self.generate_stats_section(stats)
        
        # Insere a secao apos o primeiro ## (apos o titulo principal)
        first_section_idx = readme_content.find("## ", readme_content.find("# "))
        if first_section_idx != -1:
            readme_content = readme_content[:first_section_idx] + stats_section + "\n\n" + readme_content[first_section_idx:]
        else:
            # Se nao encontrar, adiciona no final
            readme_content += "\n\n" + stats_section
        
        # Salva o README atualizado
        with open(self.readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print("README atualizado com sucesso!")
    
    def generate_stats_section(self, stats: Dict) -> str:
        """Gera a secao de estatisticas para o README"""
        stats_gerais = stats['stats_gerais']
        deck_atual = stats['deck_atual']
        deck_melhor = stats['deck_melhor']
        
        section = "## 📊 Estatísticas Atuais\n\n"
        now_utc = datetime.now(timezone.utc)
        brt_offset = timedelta(hours=-3)
        now_brt = now_utc + brt_offset
        section += f"**Última atualização:** {now_brt.strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        
        # Estatisticas gerais
        section += "### 📈 Estatísticas Gerais\n\n"
        section += f"- **Total de Batalhas:** {stats_gerais['total_batalhas']}\n"
        section += f"- **Vitórias:** {stats_gerais['vitorias']} ({stats_gerais['win_rate']:.1f}%)\n"
        section += f"- **Derrotas:** {stats_gerais['derrotas']}\n"
        section += f"- **Mudança Total de Troféus:** {int(stats_gerais['trofes_total']):+d}\n\n"
        
        # Deck atual
        if deck_atual:
            section += "### 🎴 Deck Atual (Mais Recente)\n\n"
            section += f"- **Deck:** {self.format_deck_for_readme(deck_atual['deck'])}\n"
            section += f"- **Último Resultado:** {deck_atual['ultimo_resultado'].upper()}\n"
            # Formata data do battle_time (formato ISO)
            try:
                battle_time = datetime.fromisoformat(deck_atual['battle_time'].replace('Z', '+00:00'))
                section += f"- **Data da Última Batalha:** {battle_time.strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            except:
                section += f"- **Data da Última Batalha:** {deck_atual['battle_time']}\n\n"
        else:
            section += "### 🎴 Deck Atual\n\n"
            section += "Nenhum deck encontrado no banco de dados.\n\n"
        
        # Deck com melhor win rate
        if deck_melhor:
            section += "### 🏆 Deck com Melhor Performance\n\n"
            section += f"- **Deck:** {self.format_deck_for_readme(deck_melhor['deck'])}\n"
            section += f"- **Win Rate:** {deck_melhor['win_rate']:.1f}%\n"
            section += f"- **Batalhas:** {deck_melhor['total_batalhas']} ({deck_melhor['vitorias']}V - {deck_melhor['derrotas']}D)\n"
            section += f"- **Troféus:** {int(deck_melhor['trofes_total']):+d}\n\n"
        else:
            section += "### 🏆 Deck com Melhor Performance\n\n"
            section += "Nenhum deck com estatísticas suficientes encontrado.\n\n"
        
        # O que esta funcionando e o que nao esta
        section += "### ✅ O que está funcionando\n\n"
        if deck_melhor and deck_melhor['win_rate'] >= 50:
            section += f"- ✅ **Deck com melhor performance** ({deck_melhor['win_rate']:.1f}% win rate) está acima de 50%\n"
        elif deck_melhor:
            section += f"- ⚠️ **Deck com melhor performance** ({deck_melhor['win_rate']:.1f}% win rate) está abaixo de 50%\n"
        
        if stats_gerais['win_rate'] >= 50:
            section += f"- ✅ **Win rate geral** ({stats_gerais['win_rate']:.1f}%) está acima de 50%\n"
        else:
            section += f"- ⚠️ **Win rate geral** ({stats_gerais['win_rate']:.1f}%) está abaixo de 50%\n"
        
        if stats_gerais['trofes_total'] > 0:
            section += f"- ✅ **Troféus totais** positivos (+{stats_gerais['trofes_total']})\n"
        else:
            section += f"- ⚠️ **Troféus totais** negativos ({stats_gerais['trofes_total']})\n"
        
        section += "\n### ❌ O que não está funcionando\n\n"
        
        if deck_melhor and deck_melhor['win_rate'] < 50:
            section += f"- ❌ **Deck com melhor performance** precisa de ajustes (win rate: {deck_melhor['win_rate']:.1f}%)\n"
        
        if stats_gerais['win_rate'] < 50:
            section += f"- ❌ **Win rate geral** abaixo de 50% - considere revisar estratégias\n"
        
        if stats_gerais['trofes_total'] < 0:
            section += f"- ❌ **Perda de troféus** acumulada ({stats_gerais['trofes_total']}) - precisa melhorar performance\n"
        
        if not deck_melhor or deck_melhor['total_batalhas'] < 5:
            section += "- ⚠️ **Poucos dados** - precisa de mais batalhas para análise precisa\n"
        
        return section

def main():
    """Funcao principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Atualiza README com estatisticas de decks do clash_royale.db')
    parser.add_argument('--player-tag', type=str, help='Tag do jogador (ex: #YVJR0JLY)')
    parser.add_argument('--db', type=str, default='clash_royale.db', help='Caminho do banco de dados')
    parser.add_argument('--readme', type=str, default='README.md', help='Caminho do README')
    
    args = parser.parse_args()
    
    # Tenta pegar do ambiente se nao foi passado
    player_tag = args.player_tag or os.getenv('CR_PLAYER_TAG')
    
    if not player_tag:
        print("Erro: Tag do jogador nao fornecida. Use --player-tag ou defina CR_PLAYER_TAG")
        sys.exit(1)
    
    updater = ReadmeAnalyticsUpdater(db_path=args.db, readme_path=args.readme)
    updater.update_readme(player_tag)

if __name__ == "__main__":
    main()

