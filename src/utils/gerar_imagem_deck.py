#!/usr/bin/env python3
"""
Script para gerar imagem do deck de melhor performance para o README
"""

import csv
import os
import sys
import glob
from typing import Dict, Optional
from datetime import datetime

def encontrar_csv_mais_recente() -> Optional[str]:
    """Encontra o CSV mais recente do dia"""
    csv_files = glob.glob("src/oponentes_dia_*.csv")
    if not csv_files:
        csv_files = glob.glob("oponentes_dia_*.csv")
    if not csv_files:
        return None
    return max(csv_files, key=os.path.getmtime)

def obter_deck_melhor_performance(csv_file: str) -> Optional[Dict]:
    """Obtem o deck com melhor performance do CSV"""
    if not os.path.exists(csv_file):
        return None
    
    deck_stats = {}
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
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
            if resultado in ['vitoria', 'victory']:
                deck_stats[deck]['vitorias'] += 1
            elif resultado in ['derrota', 'defeat']:
                deck_stats[deck]['derrotas'] += 1
            
            try:
                trofes = int(row.get('mudanca_trofes', 0) or 0)
                deck_stats[deck]['trofes_total'] += trofes
            except:
                pass
    
    if not deck_stats:
        return None
    
    # Encontra o deck com melhor win rate (minimo 3 batalhas)
    melhor_deck = None
    melhor_win_rate = 0
    
    for deck, stats in deck_stats.items():
        if stats['total_batalhas'] >= 3:
            win_rate = (stats['vitorias'] / stats['total_batalhas'] * 100) if stats['total_batalhas'] > 0 else 0
            if win_rate > melhor_win_rate:
                melhor_win_rate = win_rate
                melhor_deck = {
                    'deck': deck,
                    'total_batalhas': stats['total_batalhas'],
                    'vitorias': stats['vitorias'],
                    'derrotas': stats['derrotas'],
                    'win_rate': win_rate,
                    'trofes_total': stats['trofes_total']
                }
    
    # Se nao tem deck com 3+ batalhas, pega o melhor disponivel
    if not melhor_deck:
        for deck, stats in deck_stats.items():
            win_rate = (stats['vitorias'] / stats['total_batalhas'] * 100) if stats['total_batalhas'] > 0 else 0
            if win_rate > melhor_win_rate:
                melhor_win_rate = win_rate
                melhor_deck = {
                    'deck': deck,
                    'total_batalhas': stats['total_batalhas'],
                    'vitorias': stats['vitorias'],
                    'derrotas': stats['derrotas'],
                    'win_rate': win_rate,
                    'trofes_total': stats['trofes_total']
                }
    
    return melhor_deck

def gerar_svg_deck(deck_data: Dict, output_file: str = "deck_performance.svg"):
    """Gera imagem SVG do deck de melhor performance"""
    cards = deck_data['deck'].split(' | ')
    
    svg_content = f"""<svg width="800" height="400" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#667eea;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#764ba2;stop-opacity:1" />
    </linearGradient>
  </defs>
  
  <!-- Background -->
  <rect width="800" height="400" fill="url(#bgGradient)"/>
  
  <!-- Title -->
  <text x="400" y="40" font-family="Arial, sans-serif" font-size="28" font-weight="bold" fill="white" text-anchor="middle">
    Deck com Melhor Performance
  </text>
  
  <!-- Stats -->
  <text x="400" y="80" font-family="Arial, sans-serif" font-size="24" font-weight="bold" fill="white" text-anchor="middle">
    {deck_data['win_rate']:.1f}% Taxa de Vitória 
  </text>
  
  <text x="200" y="120" font-family="Arial, sans-serif" font-size="18" fill="white" text-anchor="middle">
    🏆 {deck_data['total_batalhas']} batalhas
  </text>
  <text x="400" y="120" font-family="Arial, sans-serif" font-size="18" fill="white" text-anchor="middle">
    ✅ {deck_data['vitorias']} vitórias
  </text>
  <text x="600" y="120" font-family="Arial, sans-serif" font-size="18" fill="white" text-anchor="middle">
    ❌ {deck_data['derrotas']} derrotas
  </text>
  
  <text x="300" y="150" font-family="Arial, sans-serif" font-size="18" fill="white" text-anchor="middle">
    📈 {deck_data['trofes_total']:+d} troféus
  </text>
  
  <!-- Cards -->
  <text x="400" y="200" font-family="Arial, sans-serif" font-size="20" font-weight="bold" fill="white" text-anchor="middle">
    Cartas do Deck:
  </text>
  
  <text x="400" y="240" font-family="Arial, sans-serif" font-size="16" fill="white" text-anchor="middle">
    {', '.join(cards)}
  </text>
  
  <!-- Footer -->
  <text x="400" y="380" font-family="Arial, sans-serif" font-size="12" fill="rgba(255,255,255,0.8)" text-anchor="middle">
    Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')}
  </text>
</svg>"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(svg_content)
    
    print(f"Imagem SVG gerada: {output_file}")

def main():
    """Funcao principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Gera imagem do deck de melhor performance')
    parser.add_argument('--csv', type=str, help='Caminho do CSV (ou usa o mais recente)')
    parser.add_argument('--output', type=str, default='deck_performance.svg', help='Arquivo de saida')
    
    args = parser.parse_args()
    
    csv_file = args.csv or encontrar_csv_mais_recente()
    
    if not csv_file:
        print("Erro: Nenhum CSV encontrado")
        sys.exit(1)
    
    print(f"Lendo dados de: {csv_file}")
    deck_data = obter_deck_melhor_performance(csv_file)
    
    if not deck_data:
        print("Erro: Nenhum deck encontrado no CSV")
        sys.exit(1)
    
    print(f"Deck encontrado: {deck_data['win_rate']:.1f}% win rate")
    gerar_svg_deck(deck_data, args.output)

if __name__ == "__main__":
    main()

