#!/usr/bin/env python3
"""
War Prediction Engine for Clash Royale Dashboard
Isolates mathematical calculations for war projections, decks efficiency, and enemy threat levels.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class WarPredictionEngine:
    """
    Engine responsavel por realizar os calculos preditivos de guerra baseados
    no desempenho e engajamento dos membros do clan e clans rivais.
    """
    
    MAX_DECKS_PER_DAY = 200  # 50 membros * 4 decks
    DEFAULT_EFFICIENCY = 250.0  # Pontuacao media estimada se nao houver ataques
    
    @staticmethod
    def parse_decks_used(decks_used_str: str) -> int:
        """
        Extrai a quantidade de decks jogados a partir da string decks_usados.
        Suporta formatos como "2/4", "3" ou nulos.
        """
        if not decks_used_str:
            return 0
        try:
            decks_str = str(decks_used_str).strip()
            if '/' in decks_str:
                return int(float(decks_str.split('/')[0]))
            return int(float(decks_str))
        except (ValueError, TypeError, IndexError) as e:
            # Em caso de erro de parse, loga de forma segura sem acentos
            logger.warning(f"Erro ao converter decks_usados {decks_used_str}: {e}")
            return 0

    def calculate_clan_metrics(self, player_rows: List[Dict[str, Any]], clan_name: str) -> Dict[str, Any]:
        """
        Calcula as metricas reais e as projecoes taticas para um clan especifico em um determinado dia.
        
        Args:
            player_rows: Lista de linhas de jogadores (dicionarios obtidos do CSV) daquele dia.
            clan_name: Nome do clan a ser analisado.
            
        Returns:
            Dicionario com decks_played, decks_remaining, current_fame, efficiency, e projected_fame.
        """
        clan_rows = []
        for r in player_rows:
            cn = r.get('clan_nome') or r.get('Cla', '')
            if cn and cn.strip().lower() == clan_name.strip().lower():
                clan_rows.append(r)
                
        if not clan_rows:
            logger.debug(f"Nenhum dado encontrado para o clan {clan_name}")
            return {
                'decks_played': 0,
                'decks_remaining': self.MAX_DECKS_PER_DAY,
                'current_fame': 0,
                'efficiency': 0.0,
                'projected_fame': 0
            }
            
        # 1. Obter a fama atual do clan (valor maximo de clan_fame registrado no dia)
        current_fame = 0
        for r in clan_rows:
            fame_val = r.get('clan_fame') or r.get('Fama_Hoje') or 0
            try:
                fame_int = int(float(str(fame_val).strip()))
                if fame_int > current_fame:
                    current_fame = fame_int
            except (ValueError, TypeError):
                continue
                
        # 2. Calcular decks jogados somando os ataques individuais dos membros
        decks_played = 0
        seen_players = set()
        for r in clan_rows:
            player_name = r.get('player_nome') or r.get('Jogador') or ''
            # Evita duplicar ataques se houver registros repetidos para o mesmo jogador
            if player_name and player_name not in seen_players:
                seen_players.add(player_name)
                decks_val = r.get('decks_usados') or r.get('Ataques_Feitos') or '0/4'
                decks_played += self.parse_decks_used(decks_val)
                
        # 3. Limitar decks jogados ao maximo teorico do jogo
        if decks_played > self.MAX_DECKS_PER_DAY:
            decks_played = self.MAX_DECKS_PER_DAY
            
        decks_remaining = max(0, self.MAX_DECKS_PER_DAY - decks_played)
        
        # 4. Calcular eficiencia por deck
        if decks_played > 0:
            efficiency = float(current_fame) / float(decks_played)
        else:
            efficiency = 0.0
            
        # 5. Calcular projected_fame
        # Se nao houver decks jogados, usa a pontuacao atual diretamente
        if decks_played == 0:
            projected_fame = current_fame
        else:
            projected_fame = int(current_fame + (decks_remaining * efficiency))
            
        return {
            'decks_played': decks_played,
            'decks_remaining': decks_remaining,
            'current_fame': current_fame,
            'efficiency': round(efficiency, 2),
            'projected_fame': projected_fame
        }

    def determine_threat_level(self, rival_projection: int, my_projection: int, rival_decks_remaining: int) -> str:
        """
        Classifica de forma dinamica o nivel de ameaca semaforica de um clan rival.
        
        Args:
            rival_projection: Projecao de fama final do clã rival.
            my_projection: Projecao de fama final do meu clã.
            rival_decks_remaining: Quantidade de decks restantes do rival.
            
        Returns:
            "CRITICA", "MODERADA" ou "CONTROLADA"
        """
        # Se o rival ja projetou superar a nossa projecao e restam decks dele, e Critica
        if rival_projection > my_projection:
            if rival_decks_remaining > 15:
                return "CRITICA"
            return "MODERADA"
            
        # Se a projecao do rival esta muito proxima da nossa (margem de 1500 pontos) e ele tem decks disponiveis
        margin = my_projection - rival_projection
        if margin <= 1500 and rival_decks_remaining > 20:
            return "CRITICA"
        elif margin <= 3000 and rival_decks_remaining > 10:
            return "MODERADA"
            
        return "CONTROLADA"
