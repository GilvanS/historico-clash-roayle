#!/usr/bin/env python3
"""
Resgata batalhas do arquivo mensal oponentes_mes_202604.csv
e (re)cria os arquivos diarios oponentes_dia_YYYYMMDD.csv.

- Le o mensal de abril
- Agrupa as batalhas por data (DD/MM/YYYY)
- Para cada dia: se o arquivo diario NAO existe ou tem menos registros,
  recria com todos os registros daquele dia presentes no mensal
- O arquivo mensal NAO e modificado
"""

import os
import csv
from collections import defaultdict

SRC_DIR = os.path.dirname(os.path.abspath(__file__))

MENSAL_ABRIL = os.path.join(SRC_DIR, "oponentes_mes_202604.csv")

FIELDNAMES = [
    'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente',
    'trofes_oponente', 'clan_oponente', 'resultado',
    'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
    'modo_jogo', 'tipo_batalha', 'arena',
    'deck_jogador', 'deck_oponente', 'vezes_enfrentado'
]


def detect_delimiter(filepath):
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        sample = f.read(4096)
    return ';' if sample.count(';') > sample.count(',') else ','


def read_csv(filepath):
    if not os.path.exists(filepath):
        return []
    delim = detect_delimiter(filepath)
    rows = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=delim)
        for row in reader:
            rows.append(dict(row))
    return rows


def write_csv(filepath, rows, delimiter=','):
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(
            f, fieldnames=FIELDNAMES, extrasaction='ignore', delimiter=delimiter
        )
        writer.writeheader()
        writer.writerows(rows)


def extrair_data_yyyymmdd(data_str):
    """Converte '20/04/2026 18:30' -> '20260420'"""
    try:
        partes = data_str.strip().split(' ')[0].split('/')
        dd, mm, yyyy = partes
        return f"{yyyy}{mm}{dd}"
    except Exception:
        return None


def main():
    print(f"\n{'='*60}")
    print("  RESGATE DE DIARIOS A PARTIR DO MENSAL DE ABRIL")
    print(f"{'='*60}\n")

    if not os.path.exists(MENSAL_ABRIL):
        print(f"ERRO: nao encontrei {MENSAL_ABRIL}")
        return

    # 1. Le o mensal e agrupa por dia
    registros = read_csv(MENSAL_ABRIL)
    print(f"  Mensal de abril: {len(registros)} registros lidos")

    por_dia = defaultdict(list)
    sem_data = 0
    for row in registros:
        chave = extrair_data_yyyymmdd(row.get('data', ''))
        if chave and chave.startswith('2026'):
            por_dia[chave].append(row)
        else:
            sem_data += 1

    if sem_data:
        print(f"  Aviso: {sem_data} registros sem data valida ignorados")

    print(f"  Dias distintos encontrados no mensal: {sorted(por_dia.keys())}\n")

    # 2. Para cada dia, cria/atualiza o arquivo diario
    for dia_key in sorted(por_dia.keys()):
        registros_mensal = por_dia[dia_key]
        nome_arquivo = f"oponentes_dia_{dia_key}.csv"
        path_diario = os.path.join(SRC_DIR, nome_arquivo)

        registros_existentes = read_csv(path_diario) if os.path.exists(path_diario) else []

        print(f"  {nome_arquivo}:")
        print(f"    No mensal : {len(registros_mensal)} batalhas")
        print(f"    No diario : {len(registros_existentes)} batalhas")

        if len(registros_mensal) > len(registros_existentes):
            # Mescla: usa chave data+tag+modo para deduplicar
            chaves_existentes = {
                f"{r.get('data','')}_{r.get('tag_oponente','')}_{r.get('modo_jogo','')}"
                for r in registros_existentes
            }
            novos = [
                r for r in registros_mensal
                if f"{r.get('data','')}_{r.get('tag_oponente','')}_{r.get('modo_jogo','')}"
                not in chaves_existentes
            ]
            todos = registros_existentes + novos

            # Ordena por data desc
            def parse_data(row):
                try:
                    d = row.get('data', '')
                    partes = d.split(' ')
                    dmy = partes[0].split('/')
                    hm = partes[1].split(':') if len(partes) > 1 else ['0', '0']
                    return (int(dmy[2]), int(dmy[1]), int(dmy[0]), int(hm[0]), int(hm[1]))
                except Exception:
                    return (0, 0, 0, 0, 0)

            todos.sort(key=parse_data, reverse=True)

            write_csv(path_diario, todos, delimiter=',')
            print(f"    >> ATUALIZADO: {len(todos)} batalhas gravadas ({len(novos)} novas adicionadas)")
        else:
            print(f"    >> OK: diario ja esta completo ou mais atualizado que o mensal")

    print(f"\n{'='*60}")
    print("  RESGATE CONCLUIDO!")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
