"""
Arquiva e compacta arquivos CSV antigos para economizar espaco.
Arquivos diarios e semanais mais antigos que 2 dias sao zipados na pasta 'arquivados' e depois excluidos.
"""
import os
import glob
import zipfile
from datetime import datetime, timedelta
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_csv_oficial')
ARCHIVE_DIR = os.path.join(DATA_DIR, 'arquivados')

if not os.path.exists(ARCHIVE_DIR):
    os.makedirs(ARCHIVE_DIR)

now = datetime.now()
# 2 dias de limite para arquivamento
threshold_date = now - timedelta(days=2)

def add_to_zip(zip_path, file_path, arcname):
    already_exists = False
    if os.path.exists(zip_path):
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            if arcname in zipf.namelist():
                already_exists = True
                
    if not already_exists:
        with zipfile.ZipFile(zip_path, 'a', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(file_path, arcname=arcname)

# 1. Arquivar arquivos diários
daily_files = glob.glob(os.path.join(DATA_DIR, "oponentes_dia_*.csv"))
count_daily = 0
for filepath in daily_files:
    filename = os.path.basename(filepath)
    match = re.search(r'oponentes_dia_(\d{8})\.csv', filename)
    if match:
        date_str = match.group(1)
        try:
            file_date = datetime.strptime(date_str, '%Y%m%d')
            if file_date < threshold_date:
                month_str = file_date.strftime('%Y%m')
                zip_filename = os.path.join(ARCHIVE_DIR, f"arquivados_dia_{month_str}.zip")
                print(f"Compactando {filename} em {os.path.basename(zip_filename)}...")
                add_to_zip(zip_filename, filepath, filename)
                os.remove(filepath)
                count_daily += 1
        except ValueError:
            pass

# 2. Arquivar arquivos semanais
weekly_files = glob.glob(os.path.join(DATA_DIR, "oponentes_semana_*.csv"))
count_weekly = 0
for filepath in weekly_files:
    filename = os.path.basename(filepath)
    # Para semanais, baseamos na data de modificacao do arquivo
    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
    if mtime < threshold_date:
        zip_filename = os.path.join(ARCHIVE_DIR, "arquivados_semana.zip")
        print(f"Compactando {filename} em {os.path.basename(zip_filename)}...")
        add_to_zip(zip_filename, filepath, filename)
        os.remove(filepath)
        count_weekly += 1

print(f"Processo de arquivamento concluido. {count_daily} diarios e {count_weekly} semanais arquivados.")
