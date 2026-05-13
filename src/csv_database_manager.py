import csv
import os
import logging
import re
from typing import Optional, List, Dict
from datetime import datetime

# Configuração de logging seguindo a regra de não usar acentos
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CSVManager:
    """
    Manager to handle Clash Royale CSV data processing without SQL.
    This ensures the dashboard and sync scripts always have accurate data from CSV files.
    """
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            self.data_dir = os.path.join(os.path.dirname(__file__), 'data_csv_oficial')
        else:
            self.data_dir = data_dir
            
    def load_battles(self, file_name: str = 'oponentes_ano_2026.csv') -> List[Dict]:
        """
        Loads battles from a specific CSV file.
        Returns a list of battle dictionaries.
        """
        file_path = os.path.join(self.data_dir, file_name)
        if not os.path.exists(file_path):
            logger.warning(f"Arquivo nao encontrado: {file_path}")
            return []
            
        logger.info(f"Carregando batalhas de: {file_path}")
        return self._read_csv(file_path)

    def _read_csv(self, file_path: str) -> List[Dict]:
        """Generic CSV reader with delimiter detection"""
        data = []
        try:
            delimiter = ';' # Default for official project
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                sample = f.read(2048)
                if sample.count(',') > sample.count(';'):
                    delimiter = ','
            
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                for row in reader:
                    # Filter empty rows
                    if not any(row.values()):
                        continue
                    data.append(row)
        except Exception as e:
            logger.error(f"Error reading CSV {file_path}: {e}")
        return data

    @staticmethod
    def normalize_date(date_str: str) -> Optional[str]:
        """Standardizes date format for comparison"""
        if not date_str: return None
        date_str = str(date_str).strip().strip('"').strip("'")
        
        # ISO format
        if len(date_str) >= 10 and date_str[4] == '-' and date_str[7] == '-':
            return date_str.replace('T', ' ')
            
        # BR format (DD/MM/YYYY HH:MM)
        formats = ['%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y']
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                continue
        return date_str

if __name__ == "__main__":
    # Loading test
    manager = CSVManager()
    battles = manager.load_battles()
    logger.info(f"Total battles loaded via CSV: {len(battles)}")
    if battles:
        logger.info(f"Sample record: {battles[0].get('opponent_name')} - {battles[0].get('result')}")
