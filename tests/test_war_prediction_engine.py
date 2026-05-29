#!/usr/bin/env python3
"""
Unit Tests for WarPredictionEngine
Implements structural and mathematical verification under AAA pattern (Arrange, Act, Assert).
"""

import pytest
import logging
from war_prediction_engine import WarPredictionEngine

# Configura logger de teste livre de acentos nas mensagens internas
logger = logging.getLogger(__name__)

@pytest.fixture
def engine():
    return WarPredictionEngine()

def test_parse_decks_used_various_formats(engine):
    """
    Arrange & Act & Assert
    Testa se o parsing do campo de decks usados manipula perfeitamente os formatos esperados.
    """
    logger.info("Iniciando teste de parse de decks com diversos formatos")
    assert engine.parse_decks_used("2/4") == 2
    assert engine.parse_decks_used("4/4") == 4
    assert engine.parse_decks_used("3") == 3
    assert engine.parse_decks_used("0") == 0
    assert engine.parse_decks_used("") == 0
    assert engine.parse_decks_used(None) == 0
    assert engine.parse_decks_used("invalido") == 0
    logger.info("Finalizado teste de parse de decks com sucesso")

def test_calculate_clan_metrics_empty_data(engine):
    """
    Arrange & Act & Assert
    Testa resiliencia a dados vazios, garantindo que nao ocorra divisao por zero.
    """
    logger.info("Validando resiliencia da engine com dados vazios")
    result = engine.calculate_clan_metrics([], "Tropa Do Bruxo")
    
    assert result['decks_played'] == 0
    assert result['decks_remaining'] == 200
    assert result['current_fame'] == 0
    assert result['efficiency'] == 0.0
    assert result['projected_fame'] == 0
    logger.info("Validacao de dados vazios concluida com sucesso")

def test_calculate_clan_metrics_normal_flow(engine):
    """
    Arrange
    Monta dados realistas de 3 jogadores do mesmo clan com diferentes ataques.
    """
    logger.info("Executando teste do fluxo normal de metricas de clan")
    player_data = [
        {'clan_nome': 'Tropa Do Bruxo', 'player_nome': 'PlayerA', 'decks_usados': '4/4', 'clan_fame': '1200', 'Fama_Hoje': '1200'},
        {'clan_nome': 'Tropa Do Bruxo', 'player_nome': 'PlayerB', 'decks_usados': '2/4', 'clan_fame': '1200', 'Fama_Hoje': '1200'},
        {'clan_nome': 'Tropa Do Bruxo', 'player_nome': 'PlayerC', 'decks_usados': '0/4', 'clan_fame': '1200', 'Fama_Hoje': '1200'},
        # Registro duplicado de PlayerA que deve ser ignorado pela engine
        {'clan_nome': 'Tropa Do Bruxo', 'player_nome': 'PlayerA', 'decks_usados': '4/4', 'clan_fame': '1200', 'Fama_Hoje': '1200'},
        # Jogador de clan rival que deve ser ignorado
        {'clan_nome': 'Peruvian', 'player_nome': 'RivalA', 'decks_usados': '4/4', 'clan_fame': '500', 'Fama_Hoje': '500'}
    ]
    
    # Act
    result = engine.calculate_clan_metrics(player_data, "Tropa Do Bruxo")
    
    # Assert
    # Total de decks jogados unicos: PlayerA (4) + PlayerB (2) + PlayerC (0) = 6 decks
    assert result['decks_played'] == 6
    assert result['decks_remaining'] == 194
    assert result['current_fame'] == 1200
    # Eficiencia esperada: 1200 / 6 = 200.0
    assert result['efficiency'] == 200.0
    # Projecao esperada: 1200 + (194 * 200) = 1200 + 38800 = 40000
    assert result['projected_fame'] == 40000
    logger.info("Fluxo normal validado e homologado com sucesso")

def test_calculate_clan_metrics_exceeds_max_decks(engine):
    """
    Arrange
    Simula uma situacao de contorno onde os dados computados excedem 200 ataques.
    """
    logger.info("Executando teste de limite de decks maximos do jogo")
    player_data = []
    # Cria 55 jogadores virtuais com 4 decks cada (55 * 4 = 220 decks)
    for i in range(55):
        player_data.append({
            'clan_nome': 'Tropa Do Bruxo',
            'player_nome': f'Player_{i}',
            'decks_usados': '4/4',
            'clan_fame': '45000'
        })
        
    # Act
    result = engine.calculate_clan_metrics(player_data, "Tropa Do Bruxo")
    
    # Assert
    # Deve truncar os decks jogados em 200
    assert result['decks_played'] == 200
    assert result['decks_remaining'] == 0
    assert result['projected_fame'] == 45000  # Se decks_remaining e 0, a projecao e igual a fama atual
    logger.info("Teste de limite maximo concluido com sucesso")

def test_determine_threat_level_scenarios(engine):
    """
    Arrange & Act & Assert
    Testa a escala semaforica de ameacas conforme as projecoes matematicas comparativas.
    """
    logger.info("Iniciando validacao da escala semaforica de ameacas")
    
    # Caso 1: Rival a frente na projecao e com decks para jogar -> Critica
    assert engine.determine_threat_level(rival_projection=35000, my_projection=30000, rival_decks_remaining=20) == "CRITICA"
    
    # Caso 2: Rival a frente mas com pouquissimos decks restantes (menos de 15) -> Moderada
    assert engine.determine_threat_level(rival_projection=32000, my_projection=30000, rival_decks_remaining=10) == "MODERADA"
    
    # Caso 3: Rival atras, mas a margem e pequena (ex: 800) e ele tem muitos decks para jogar (ex: 25) -> Critica
    assert engine.determine_threat_level(rival_projection=29200, my_projection=30000, rival_decks_remaining=25) == "CRITICA"
    
    # Caso 4: Rival atras, margem media (ex: 2000) e decks restantes medios -> Moderada
    assert engine.determine_threat_level(rival_projection=28000, my_projection=30000, rival_decks_remaining=15) == "MODERADA"
    
    # Caso 5: Rival atras com grande margem de diferenca -> Controlada
    assert engine.determine_threat_level(rival_projection=20000, my_projection=30000, rival_decks_remaining=5) == "CONTROLADA"
    logger.info("Escala semaforica de ameaca homologada com sucesso")
