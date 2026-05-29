import os
import csv
import sys

FIELDNAMES_28 = [
    'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente',
    'trofes_oponente', 'clan_oponente', 'resultado',
    'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
    'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente', 'vezes_enfrentado',
    'elixir_vazado_jogador', 'elixir_vazado_oponente', 'nivel_torre_jogador',
    'vida_torre_rei_jogador', 'vida_torre_rei_oponente', 
    'vida_torres_princesa_jogador', 'vida_torres_princesa_oponente',
    'trofes_iniciais_jogador', 'trofes_finais_jogador',
    'posicao_global_jogador', 'posicao_global_oponente', 'nivel_torre_oponente'
]

# Mapeamento do formato antigo (19 colunas) para o novo (28 colunas)
# Antigo: data;nome_oponente;tag_oponente;nivel_oponente;trofes_oponente;clan_oponente;resultado;coroas_jogador;coroas_oponente;mudanca_trofes;modo_jogo;tipo_batalha;arena;deck_jogador;deck_oponente;vezes_enfrentado;elixir_vazado_jogador;elixir_vazado_oponente;nivel_torre_jogador
FIELDNAMES_19 = [
    'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente',
    'trofes_oponente', 'clan_oponente', 'resultado',
    'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
    'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente', 'vezes_enfrentado',
    'elixir_vazado_jogador', 'elixir_vazado_oponente', 'nivel_torre_jogador'
]

def repair_csv():
    file_path = r'a:\Workspace\historico-clash-roayle\src\data_csv_oficial\oponentes_ano_2026.csv'
    backup_path = file_path + '.bak'
    
    if not os.path.exists(file_path):
        print("Arquivo nao encontrado.")
        return

    print(f"Iniciando reparo de {file_path}...")
    
    # Criar backup
    import shutil
    shutil.copy2(file_path, backup_path)
    
    repaired_rows = []
    seen = set()
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        # Lemos as linhas brutas para tratar variacoes de colunas
        lines = f.readlines()
        
    header = lines[0].strip().split(';')
    print(f"Colunas no cabecalho: {len(header)}")
    
    for i, line in enumerate(lines[1:], 1):
        cols = line.strip().split(';')
        
        # Ignora linhas vazias
        if not any(cols): continue
        
        row_dict = {}
        
        if len(cols) == 19:
            # Formato antigo
            for j, val in enumerate(cols):
                row_dict[FIELDNAMES_19[j]] = val
            # Preenche novos campos com default
            for field in FIELDNAMES_28:
                if field not in row_dict:
                    row_dict[field] = '0' if 'trofes' in field or 'vida' in field or 'nivel' in field else 'N/A'
        
        elif len(cols) >= 28:
            # Formato novo (pode ter colunas extras que ignoramos)
            for j, field in enumerate(FIELDNAMES_28):
                row_dict[field] = cols[j]
        
        else:
            # Formato desconhecido (tenta mapear o que der)
            print(f"Linha {i} com numero inesperado de colunas: {len(cols)}. Tentando salvar o que for possivel.")
            for j, val in enumerate(cols):
                if j < len(FIELDNAMES_28):
                    row_dict[FIELDNAMES_28[j]] = val
            # Completa o resto
            for field in FIELDNAMES_28:
                if field not in row_dict:
                    row_dict[field] = '0'
        
        # SANITIZACAO CRITICA: Se o campo de trofeus contem '#', ele esta desalinhado
        # Normalmente o ID (#...) esta na coluna 2 (tag_oponente) ou 25/26 (posicao_global)
        if '#' in str(row_dict.get('trofes_iniciais_jogador', '')):
            print(f"Detectado ID em trofes na linha {i}. Limpando...")
            row_dict['trofes_iniciais_jogador'] = '0'
            
        if '#' in str(row_dict.get('torres_destruidas', '')): # Caso exista esse campo algum dia
            row_dict['torres_destruidas'] = '0'

        # Deduplicacao
        dt = row_dict.get('data', '')
        opp = row_dict.get('tag_oponente', '')
        key = (dt, opp)
        
        if key in seen:
            continue
        seen.add(key)
        repaired_rows.append(row_dict)

    # Escreve arquivo limpo
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES_28, delimiter=';')
        writer.writeheader()
        writer.writerows(repaired_rows)
        
    print(f"Reparo concluido. {len(repaired_rows)} registros salvos.")

if __name__ == "__main__":
    repair_csv()
