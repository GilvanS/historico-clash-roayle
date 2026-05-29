import os
import csv

FIELDNAMES = [
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

DATA_DIR = 'data/csv'

def migrate():
    if not os.path.exists(DATA_DIR):
        print("Diretorio nao encontrado.")
        return

    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.csv'):
            file_path = os.path.join(DATA_DIR, filename)
            print(f"Migrando {filename}...")
            
            rows = []
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    rows = list(reader)
                
                if not rows:
                    continue

                # Escreve de volta com o novo header
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=';', extrasaction='ignore')
                    writer.writeheader()
                    for row in rows:
                        # Preenche campos novos com 'N/A' ou 0 se nao existirem
                        for field in FIELDNAMES:
                            if field not in row:
                                row[field] = 'N/A' if 'posicao' in field else 0
                        writer.writerow(row)
                print(f"  {filename} migrado com sucesso.")
            except Exception as e:
                print(f"  Erro ao migrar {filename}: {e}")

if __name__ == "__main__":
    migrate()
