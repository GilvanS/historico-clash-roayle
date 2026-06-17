"""
Arquiva CSVs diários e semanais antigos em ZIPs organizados por mês.
Configurável via variável de ambiente CSV_ARCHIVE_DAYS (padrão: 90 dias).
Destino: data/backups/archive/YYYY-MM/
"""
import os
import glob
import zipfile
import re
import sys
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_DAYS = int(os.getenv('CSV_ARCHIVE_DAYS', '90'))
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'data', 'csv')
_BACKUP_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'data', 'backups', 'archive')


def _add_to_zip(zip_path: str, file_path: str, arcname: str) -> None:
    existing = set()
    if os.path.exists(zip_path):
        with zipfile.ZipFile(zip_path, 'r') as zf:
            existing = set(zf.namelist())
    if arcname not in existing:
        with zipfile.ZipFile(zip_path, 'a', zipfile.ZIP_DEFLATED) as zf:
            zf.write(file_path, arcname=arcname)


def run(days: int = _DAYS, data_dir: str = _DATA_DIR, backup_root: str = _BACKUP_ROOT) -> dict:
    threshold = datetime.now() - timedelta(days=days)
    counts = {'daily': 0, 'weekly': 0}

    for filepath in glob.glob(os.path.join(data_dir, 'oponentes_dia_*.csv')):
        filename = os.path.basename(filepath)
        m = re.search(r'oponentes_dia_(\d{8})\.csv', filename)
        if not m:
            continue
        try:
            file_date = datetime.strptime(m.group(1), '%Y%m%d')
        except ValueError:
            continue
        if file_date >= threshold:
            continue
        month_dir = os.path.join(backup_root, file_date.strftime('%Y-%m'))
        os.makedirs(month_dir, exist_ok=True)
        zip_path = os.path.join(month_dir, f"diarios_{file_date.strftime('%Y%m')}.zip")
        print(f"  arquivando {filename} -> {os.path.relpath(zip_path)}")
        _add_to_zip(zip_path, filepath, filename)
        os.remove(filepath)
        counts['daily'] += 1

    for filepath in glob.glob(os.path.join(data_dir, 'oponentes_semana_*.csv')):
        filename = os.path.basename(filepath)
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        if mtime >= threshold:
            continue
        month_dir = os.path.join(backup_root, mtime.strftime('%Y-%m'))
        os.makedirs(month_dir, exist_ok=True)
        zip_path = os.path.join(month_dir, f"semanais_{mtime.strftime('%Y%m')}.zip")
        print(f"  arquivando {filename} -> {os.path.relpath(zip_path)}")
        _add_to_zip(zip_path, filepath, filename)
        os.remove(filepath)
        counts['weekly'] += 1

    print(f"Arquivamento concluido: {counts['daily']} diarios, {counts['weekly']} semanais (limite: {days} dias)")
    return counts


if __name__ == '__main__':
    run()
