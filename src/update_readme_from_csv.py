#!/usr/bin/env python3
"""
Script para atualizar o README com estatisticas lidas dos CSVs de oponentes
"""

import csv
import os
import sys
import glob
from typing import Dict, List, Optional
from collections import Counter
from datetime import datetime

class ReadmeCSVUpdater:
    def __init__(self, csv_dir: str = "src", readme_path: str = "README.md"):
        self.csv_dir = csv_dir
        self.readme_path = readme_path
    
    def find_latest_csv(self, pattern: str = "oponentes_dia_*.csv") -> Optional[str]:
        """Encontra o CSV mais recente do dia"""
        csv_files = glob.glob(os.path.join(self.csv_dir, pattern))
        if not csv_files:
            return None
        # Retorna o mais recente (por nome ou data de modificacao)
        return max(csv_files, key=os.path.getmtime)
    
    def read_csv_data(self, csv_file: str) -> List[Dict]:
        """Le dados do CSV"""
        if not os.path.exists(csv_file):
            return []
        
        data = []
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        
        return data
    
    def get_deck_stats_from_csv(self, csv_file: str) -> Dict:
        """Analisa estatisticas de decks do CSV"""
        data = self.read_csv_data(csv_file)
        
        if not data:
            return None
        
        # Deck atual (mais recente - ultima linha do CSV)
        deck_atual = None
        if data:
            ultima_batalha = data[-1]
            deck_atual = {
                'deck': ultima_batalha.get('deck_jogador', ''),
                'ultimo_resultado': ultima_batalha.get('resultado', ''),
                'data': ultima_batalha.get('data', '')
            }
        
        # Estatisticas por deck
        deck_stats = {}
        for row in data:
            deck = row.get('deck_jogador', '')
            if not deck:
                continue
            
            if deck not in deck_stats:
                deck_stats[deck] = {
                    'total_batalhas': 0,
                    'vitorias': 0,
                    'derrotas': 0,
                    'trofes_total': 0
                }
            
            deck_stats[deck]['total_batalhas'] += 1
            resultado = row.get('resultado', '').lower()
            if resultado in ['victory', 'vitoria']:
                deck_stats[deck]['vitorias'] += 1
            elif resultado in ['defeat', 'derrota']:
                deck_stats[deck]['derrotas'] += 1
            
            try:
                trofes = int(row.get('mudanca_trofes', 0) or 0)
                deck_stats[deck]['trofes_total'] += trofes
            except:
                pass
        
        # Converte para lista e calcula win rate
        decks_stats = []
        for deck, stats in deck_stats.items():
            win_rate = (stats['vitorias'] / stats['total_batalhas'] * 100) if stats['total_batalhas'] > 0 else 0
            decks_stats.append({
                'deck': deck,
                'total_batalhas': stats['total_batalhas'],
                'vitorias': stats['vitorias'],
                'derrotas': stats['derrotas'],
                'win_rate': win_rate,
                'trofes_total': stats['trofes_total']
            })
        
        # Ordena por win rate
        decks_stats.sort(key=lambda x: (x['win_rate'], x['total_batalhas']), reverse=True)
        
        # Estatisticas gerais
        total_batalhas = len(data)
        vitorias = sum(1 for row in data if row.get('resultado', '').lower() in ['victory', 'vitoria'])
        derrotas = sum(1 for row in data if row.get('resultado', '').lower() in ['defeat', 'derrota'])
        win_rate_geral = (vitorias / total_batalhas * 100) if total_batalhas > 0 else 0
        
        try:
            trofes_total = sum(int(row.get('mudanca_trofes', 0) or 0) for row in data)
        except:
            trofes_total = 0
        
        stats_gerais = {
            'total_batalhas': total_batalhas,
            'vitorias': vitorias,
            'derrotas': derrotas,
            'win_rate': win_rate_geral,
            'trofes_total': trofes_total
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
        # O formato do deck é "Card1 | Card2 | Card3 | ..."
        cards = deck_string.split(' | ')
        return ", ".join(cards)
    
    def get_recent_battles(self, csv_file: str, limit: int = 10) -> List[Dict]:
        """Obtem as ultimas batalhas do CSV"""
        data = self.read_csv_data(csv_file)
        if not data:
            return []
        
        # Retorna as ultimas batalhas (CSV esta ordenado por data)
        recent = data[-limit:] if len(data) > limit else data
        return list(reversed(recent))  # Mais recente primeiro
    
    def update_readme(self, csv_file: Optional[str] = None):
        """Atualiza o README com as estatisticas do CSV"""
        if not csv_file:
            csv_file = self.find_latest_csv()
        
        if not csv_file or not os.path.exists(csv_file):
            print(f"CSV nao encontrado: {csv_file}")
            return
        
        print(f"Lendo dados de: {csv_file}")
        stats = self.get_deck_stats_from_csv(csv_file)
        
        if not stats or not stats['stats_gerais']:
            print("Nenhuma estatistica encontrada no CSV")
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
        recent_battles = self.get_recent_battles(csv_file, 5)
        stats_section = self.generate_stats_section(stats, recent_battles)
        
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
    
    def generate_stats_section(self, stats: Dict, recent_battles: List[Dict]) -> str:
        """Gera a secao de estatisticas para o README"""
        stats_gerais = stats['stats_gerais']
        deck_atual = stats['deck_atual']
        deck_melhor = stats['deck_melhor']
        
        section = "## 📊 Estatísticas Atuais\n\n"
        section += f"**Última atualização:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        
        # Estatisticas gerais
        section += "### 📈 Estatísticas Gerais\n\n"
        section += f"- **Total de Batalhas:** {stats_gerais['total_batalhas']}\n"
        section += f"- **Vitórias:** {stats_gerais['vitorias']} ({stats_gerais['win_rate']:.1f}%)\n"
        section += f"- **Derrotas:** {stats_gerais['derrotas']}\n"
        section += f"- **Mudança Total de Troféus:** {stats_gerais['trofes_total']:+d}\n\n"
        
        # Deck atual
        if deck_atual and deck_atual['deck']:
            section += "### 🎴 Deck Atual (Mais Recente)\n\n"
            section += f"- **Deck:** {self.format_deck_for_readme(deck_atual['deck'])}\n"
            section += f"- **Último Resultado:** {deck_atual['ultimo_resultado'].upper()}\n"
            section += f"- **Data da Última Batalha:** {deck_atual['data']}\n\n"
        else:
            section += "### 🎴 Deck Atual\n\n"
            section += "Nenhum deck encontrado no CSV.\n\n"
        
        # Deck com melhor win rate
        if deck_melhor:
            section += "### 🏆 Deck com Melhor Performance\n\n"
            section += f"- **Deck:** {self.format_deck_for_readme(deck_melhor['deck'])}\n"
            section += f"- **Win Rate:** {deck_melhor['win_rate']:.1f}%\n"
            section += f"- **Batalhas:** {deck_melhor['total_batalhas']} ({deck_melhor['vitorias']}V - {deck_melhor['derrotas']}D)\n"
            section += f"- **Troféus:** {deck_melhor['trofes_total']:+d}\n\n"
        else:
            section += "### 🏆 Deck com Melhor Performance\n\n"
            section += "Nenhum deck com estatísticas suficientes encontrado.\n\n"
        
        # Ultimas batalhas
        if recent_battles:
            section += "### ⚔️ Últimas Batalhas\n\n"
            for i, battle in enumerate(recent_battles[:5], 1):
                resultado = battle.get('resultado', '').upper()
                resultado_emoji = "✅" if resultado == "VICTORY" else "❌" if resultado == "DEFEAT" else "⚖️"
                oponente = battle.get('nome_oponente', 'Desconhecido')
                coroas_jogador = battle.get('coroas_jogador', '0')
                coroas_oponente = battle.get('coroas_oponente', '0')
                try:
                    trofes = int(battle.get('mudanca_trofes', '0') or '0')
                    trofes_str = f"{trofes:+d}"
                except:
                    trofes_str = battle.get('mudanca_trofes', '0')
                data_batalha = battle.get('data', '')
                
                section += f"{i}. {resultado_emoji} **{resultado}** vs {oponente} - {coroas_jogador}-{coroas_oponente} coroas ({trofes_str} troféus) - {data_batalha}\n"
            section += "\n"
        
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
    
    parser = argparse.ArgumentParser(description='Atualiza README com estatisticas dos CSVs')
    parser.add_argument('--csv', type=str, help='Caminho do CSV (ou usa o mais recente do dia)')
    parser.add_argument('--csv-dir', type=str, default='src', help='Diretorio dos CSVs')
    parser.add_argument('--readme', type=str, default='README.md', help='Caminho do README')
    
    args = parser.parse_args()
    
    updater = ReadmeCSVUpdater(csv_dir=args.csv_dir, readme_path=args.readme)
    updater.update_readme(csv_file=args.csv)

if __name__ == "__main__":
    main()
