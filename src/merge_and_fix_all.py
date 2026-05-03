import csv
import os
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

DATA_DIR = "src/data_csv_oficial"
FILE_ANUAL = os.path.join(DATA_DIR, "oponentes_ano_2026.csv")
FILE_RESTAURADO = os.path.join(DATA_DIR, "backups/oponentes_ano_2026_restaurado.csv")
FILE_RECUPERADO = os.path.join(DATA_DIR, "backups/oponentes_2026_backup_recuperado.csv")

# Colunas oficiais esperadas pelo Dashboard (29 colunas agora com player_tag)
COLUMNS = [
    "data", "oponente_nome", "oponente_tag", "coroa_jogador", "coroa_oponente",
    "oponente_cla", "resultado", "vitoria", "derrota", "empate",
    "modo_jogo", "tipo_luta", "arena", "meu_deck", "deck_oponente",
    "minhas_evolucao", "media_elixir_jogador", "media_elixir_oponente", "total_elixir_jogador",
    "vida_torre_rei_jogador", "vida_torre_rei_oponente", "vida_torres_princesa_jogador", "vida_torres_princesa_oponente",
    "trofes_iniciais_jogador", "trofes_finais_jogador", "posicao_global_jogador", "posicao_global_oponente", "nivel_torre_oponente",
    "player_tag"
]

# Mapeamento de colunas antigas para novas
MAPPING = {
    "nome_oponente": "oponente_nome",
    "tag_oponente": "oponente_tag",
    "coroas_jogador": "coroa_jogador",
    "coroas_oponente": "coroa_oponente",
    "clan_oponente": "oponente_cla",
    "tipo_batalha": "tipo_luta",
    "deck_jogador": "meu_deck"
}

def make_dedup_key(row):
    return f"{row.get('data', '').strip()}_{row.get('oponente_tag', '').strip()}"

def load_csv(file_path):
    data = []
    if not os.path.exists(file_path):
        log.warning(f"Arquivo nao encontrado: {file_path}")
        return data
    
    encodings = ['utf-8-sig', 'utf-8', 'utf-16', 'latin-1']
    for enc in encodings:
        try:
            with open(file_path, mode='r', encoding=enc) as f:
                # Detectar delimitador
                sample = f.read(8192)
                f.seek(0)
                dialect = csv.Sniffer().sniff(sample) if ',' in sample or ';' in sample else None
                delimiter = dialect.delimiter if dialect else ';'
                if ';' in sample: delimiter = ';' # Força se houver ;
                
                f.seek(0)
                reader = csv.DictReader(f, delimiter=delimiter)
                
                for row in reader:
                    new_row = {}
                    for col in COLUMNS:
                        # Tenta pegar valor direto ou via mapeamento
                        val = row.get(col)
                        if val is None:
                            # Tenta mapear nomes antigos
                            old_key = next((k for k, v in MAPPING.items() if v == col), None)
                            if old_key:
                                val = row.get(old_key)
                        
                        # Fallbacks
                        if val is None:
                            if col == 'player_tag':
                                val = "#2QR292P"
                            elif any(x in col for x in ["vida", "posicao", "trofes", "vitoria", "derrota", "empate"]):
                                val = "0"
                            else:
                                val = "N/A"
                        
                        new_row[col] = val
                    
                    # Normalização de resultado e flags
                    res = str(new_row["resultado"]).lower()
                    if "vitoria" in res or "victory" in res:
                        new_row["vitoria"], new_row["derrota"], new_row["empate"] = "1", "0", "0"
                    elif "derrota" in res or "defeat" in res:
                        new_row["vitoria"], new_row["derrota"], new_row["empate"] = "0", "1", "0"
                    elif "empate" in res or "draw" in res:
                        new_row["vitoria"], new_row["derrota"], new_row["empate"] = "0", "0", "1"

                    data.append(new_row)
                
                log.info(f"Carregados {len(data)} registros de {file_path} (enc: {enc}, delim: '{delimiter}')")
                return data
        except Exception:
            continue
    
    return data

def main():
    log.info("Iniciando processo de recuperacao final...")
    
    # 1. Carregar dados
    restaurados = load_csv(FILE_RESTAURADO)
    recuperados = load_csv(FILE_RECUPERADO)
    
    # 2. Mesclar
    all_data = {}
    for row in restaurados:
        key = make_dedup_key(row)
        if key: all_data[key] = row
            
    added = 0
    updated = 0
    for row in recuperados:
        key = make_dedup_key(row)
        if not key: continue
        
        if key not in all_data:
            all_data[key] = row
            added += 1
        else:
            # Atualiza se tiver dados premium (vida da torre)
            if row.get("vida_torre_rei_jogador") not in ["N/A", "0", ""]:
                all_data[key].update(row)
                updated += 1
    
    log.info(f"Fim do merge. Total unico: {len(all_data)} (Novos: {added}, Atualizados: {updated})")
    
    # 3. Salvar
    final_list = sorted(all_data.values(), key=lambda x: x['data'], reverse=True)
    try:
        with open(FILE_ANUAL, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=';')
            writer.writeheader()
            writer.writerows(final_list)
        log.info(f"Sucesso: {FILE_ANUAL} atualizado.")
    except Exception as e:
        log.error(f"Erro ao salvar: {e}")

if __name__ == "__main__":
    main()
