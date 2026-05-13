#!/usr/bin/env python3
"""
Script de migracao: Adiciona coluna 'player_tag' ao CSV oponentes_ano_2026.csv.
Preenche todas as linhas existentes com a tag da conta principal (#2QR292P).

Este script e ONE-SHOT: rode uma vez, valide o resultado, e depois pode ser removido.
"""

import os
import csv
import shutil
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_csv_oficial')
CSV_FILE = os.path.join(DATA_DIR, 'oponentes_ano_2026.csv')
PRIMARY_TAG = '#2QR292P'

def main():
    if not os.path.exists(CSV_FILE):
        print(f"[ERRO] Arquivo nao encontrado: {CSV_FILE}")
        return

    # 1. Backup de seguranca antes de qualquer alteracao
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{CSV_FILE}.bak_migration_{timestamp}"
    shutil.copy2(CSV_FILE, backup_path)
    print(f"[OK] Backup criado: {backup_path}")

    # 2. Ler CSV existente
    rows = []
    original_fieldnames = []
    with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        original_fieldnames = reader.fieldnames or []
        for row in reader:
            rows.append(row)

    total = len(rows)
    print(f"[INFO] {total} linhas lidas do CSV.")

    # 3. Verificar se a coluna ja existe
    if 'player_tag' in original_fieldnames:
        # Verifica se ha linhas vazias
        empty_count = sum(1 for r in rows if not r.get('player_tag', '').strip())
        if empty_count == 0:
            print("[INFO] Coluna 'player_tag' ja existe e todas as linhas estao preenchidas. Nada a fazer.")
            return
        else:
            print(f"[INFO] Coluna 'player_tag' existe mas {empty_count} linhas estao vazias. Preenchendo...")
            for row in rows:
                if not row.get('player_tag', '').strip():
                    row['player_tag'] = PRIMARY_TAG
    else:
        # 4. Adicionar coluna player_tag como PRIMEIRA coluna
        print(f"[INFO] Adicionando coluna 'player_tag' com valor '{PRIMARY_TAG}' em todas as {total} linhas...")
        for row in rows:
            row['player_tag'] = PRIMARY_TAG

    # 5. Montar novo header com player_tag como primeira coluna
    new_fieldnames = ['player_tag'] + [f for f in original_fieldnames if f != 'player_tag']

    # 6. Reescrever CSV com a nova coluna
    with open(CSV_FILE, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames, delimiter=';', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] CSV atualizado com sucesso! {total} linhas com 'player_tag' = '{PRIMARY_TAG}'")
    print(f"[INFO] Novo header: {';'.join(new_fieldnames[:5])}... ({len(new_fieldnames)} colunas)")

    # 7. Validacao rapida: reler e confirmar
    with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        check_rows = list(reader)
        assert len(check_rows) == total, f"ERRO: Contagem diferiu! Esperado {total}, lido {len(check_rows)}"
        assert all(r.get('player_tag') == PRIMARY_TAG for r in check_rows), "ERRO: Nem todas as linhas tem player_tag!"
        print(f"[VALIDACAO OK] {len(check_rows)} linhas confirmadas com player_tag correto.")


if __name__ == '__main__':
    main()
