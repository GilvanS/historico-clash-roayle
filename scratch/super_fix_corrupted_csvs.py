import os
import re
import csv

def super_fix():
    correct_header = [
        "data", "nome_oponente", "tag_oponente", "nivel_oponente", "trofes_oponente",
        "clan_oponente", "resultado", "coroas_jogador", "coroas_oponente", "mudanca_trofes",
        "modo_jogo", "tipo_batalha", "arena", "deck_jogador", "deck_oponente", "vezes_enfrentado"
    ]
    
    directory = "src/data_csv_oficial"
    all_records = []
    
    # Regex para capturar uma linha que pareça um registro de batalha
    # Procura por data DD/MM/YYYY HH:MM ou YYYY-MM-DD HH:MM
    date_pattern = re.compile(r'(\d{2}/\d{2}/\d{4} \d{2}:\d{2}|\d{4}-\d{2}-\d{2} \d{2}:\d{2})')

    print("Iniciando reconstrução total dos dados (V2 - Deep Scan)...")
    
    for filename in os.listdir(directory):
        if filename.endswith(".csv") and "oponentes" in filename:
            filepath = os.path.join(directory, filename)
            print(f"Processando {filename}...")
            
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Remove marcadores de conflito brutos
            content = re.sub(r'<<<<<<<.*?=======.*?>>>>>>>', '', content, flags=re.DOTALL)
            
            # Encontra todos os índices de início de datas
            matches = list(date_pattern.finditer(content))
            
            for i in range(len(matches)):
                start = matches[i].start()
                # O fim é o início do próximo registro ou o fim do arquivo
                end = matches[i+1].start() if i + 1 < len(matches) else len(content)
                
                segment = content[start:end].strip()
                if not segment: continue
                
                # Limpeza de lixo dentro do segmento (headers, etc)
                garbage_markers = ["vezes_enfrentado", "data,", "nome_oponente", "<<<<<<<", "=======", ">>>>>>>"]
                for marker in garbage_markers:
                    if marker in segment:
                        segment = segment.split(marker)[0].strip()
                
                segment = segment.strip(',')
                
                # Extração via CSV reader
                reader = csv.reader([segment])
                try:
                    row = next(reader)
                    if len(row) >= 15:
                        clean_row = [col.strip() for col in row[:16]]
                        if len(clean_row) == 15:
                            clean_row.append("1")
                        
                        # Validação final: a data deve bater com o padrão
                        if date_pattern.match(clean_row[0]):
                            all_records.append(clean_row)
                except:
                    continue

    print(f"Total de registros recuperados: {len(all_records)}")
    
    records_by_year = {}
    for rec in all_records:
        date_str = rec[0]
        year_match = re.search(r'(\d{4})', date_str)
        if year_match:
            year = year_match.group(1)
            if year not in records_by_year:
                records_by_year[year] = []
            records_by_year[year].append(rec)

    for year, recs in records_by_year.items():
        # Deduplicação rigorosa (Data + Tag + Resultado)
        unique_recs = []
        seen = set()
        for r in recs:
            # Normaliza data para evitar diferenças de format
            norm_date = r[0].replace('-', '/')
            key = (norm_date, r[2], r[6].lower())
            if key not in seen:
                unique_recs.append(r)
                seen.add(key)
        
        output_file = os.path.join(directory, f"oponentes_ano_{year}.csv")
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(correct_header)
            # Ordena por data decrescente
            unique_recs.sort(key=lambda x: x[0], reverse=True)
            writer.writerows(unique_recs)
        print(f"Salvo {output_file} com {len(unique_recs)} registros únicos.")

if __name__ == "__main__":
    super_fix()
