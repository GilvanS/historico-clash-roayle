import pandas as pd
import os
from datetime import datetime, timedelta
import logging

# Configuracao de logging sem acentos conforme as regras
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def normalize_result(res):
    if not isinstance(res, str): return res
    res = res.lower().strip()
    mapping = {
        'vitoria': 'victory',
        'derrota': 'defeat',
        'empate': 'draw',
        'victory': 'victory',
        'defeat': 'defeat',
        'draw': 'draw'
    }
    return mapping.get(res, res)

def deduplicate_csv(file_path):
    if not os.path.exists(file_path):
        logger.warning(f"Arquivo nao encontrado: {file_path}")
        return

    logger.info(f"Processando arquivo: {file_path}")
    
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        logger.error(f"Erro ao ler {file_path}: {e}")
        return

    if df.empty:
        logger.info(f"Arquivo vazio: {file_path}")
        return

    # Normalizar resultados para comparacao
    df['resultado_norm'] = df['resultado'].apply(normalize_result)
    
    # Converter data para datetime
    def parse_date(date_str):
        for fmt in ('%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S'):
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        return None

    df['dt_parsed'] = df['data'].apply(parse_date)
    
    # Ordenar por data
    df = df.sort_values(by=['tag_oponente', 'dt_parsed'])
    
    initial_count = len(df)
    to_keep_indices = []
    
    # Agrupar por oponente
    for tag, group in df.groupby('tag_oponente'):
        group = group.sort_values('dt_parsed')
        last_battle_idx = None
        
        for idx, row in group.iterrows():
            if last_battle_idx is None:
                to_keep_indices.append(idx)
                last_battle_idx = idx
                continue
            
            last_battle = df.loc[last_battle_idx]
            
            # Critérios de duplicidade relaxados para capturar problemas de timezone e coletas repetidas
            time_diff = abs((row['dt_parsed'] - last_battle['dt_parsed']).total_seconds() / 60)
            same_result = row['resultado_norm'] == last_battle['resultado_norm']
            
            # Mudanca de trofeus e coroas sao indicadores fortes
            try:
                same_trophies = float(row['mudanca_trofes']) == float(last_battle['mudanca_trofes'])
            except:
                same_trophies = str(row['mudanca_trofes']) == str(last_battle['mudanca_trofes'])
                
            same_crowns = (int(row['coroas_jogador']) == int(last_battle['coroas_jogador']) and 
                           int(row['coroas_oponente']) == int(last_battle['coroas_oponente']))
            
            is_duplicate = False
            
            # Se for o mesmo resultado e mesmas coroas dentro de um periodo de 4 horas
            if same_result and same_crowns and time_diff <= 240:
                # Se alem disso for a mesma mudanca de trofeus, e 99% de chance de ser duplicata
                if same_trophies or time_diff < 10 or abs(time_diff - 180) < 10:
                    is_duplicate = True

            if is_duplicate:
                logger.info(f"Duplicata detectada: {row['nome_oponente']} ({tag}) em {row['data']} vs {last_battle['data']}")
                
                # Heuristica: Manter o registro que parece ter mais informacao util
                # Por exemplo, se um tem nivel > 0 e o outro nao
                if int(row['nivel_oponente']) > int(last_battle['nivel_oponente']):
                    # Substitui o anterior pelo atual
                    to_keep_indices.remove(last_battle_idx)
                    to_keep_indices.append(idx)
                    last_battle_idx = idx
                elif len(str(row['deck_oponente'])) > len(str(last_battle['deck_oponente'])) and int(last_battle['nivel_oponente']) <= int(row['nivel_oponente']):
                    # Se o deck parece mais completo e o nivel nao e pior
                    to_keep_indices.remove(last_battle_idx)
                    to_keep_indices.append(idx)
                    last_battle_idx = idx
                else:
                    # Mantem o anterior, ignora o atual
                    pass
            else:
                to_keep_indices.append(idx)
                last_battle_idx = idx

    # Filtrar o DataFrame original usando os indices selecionados
    df_clean = df.loc[to_keep_indices].drop(columns=['resultado_norm', 'dt_parsed'])
    
    # Salvar de volta
    df_clean.to_csv(file_path, index=False)
    
    final_count = len(df_clean)
    logger.info(f"Concluido: {file_path}. Removidas {initial_count - final_count} duplicatas.")

def main():
    directory = 'data/csv'
    # Incluir arquivos anuais e o arquivo de limpeza
    files = [f for f in os.listdir(directory) if f.startswith('oponentes_ano_') and f.endswith('.csv')]
    
    for file in files:
        deduplicate_csv(os.path.join(directory, file))

if __name__ == "__main__":
    main()
