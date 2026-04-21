#!/usr/bin/env python3
"""
Consolida os arquivos diarios de janeiro, fevereiro e marco 2026
nos seus respectivos arquivos mensais (oponentes_mes_202601.csv, etc.)
e remove os arquivos diarios apos a consolidacao.

Regras:
- Sem duplicatas: chave = data + tag_oponente + modo_jogo
- Recalcula vezes_enfrentado com base no total do mes consolidado
- Deleta os diarios de jan/fev/mar apos consolidar com sucesso
- Diarios de abril ficam intactos (mes em andamento)
"""

import os
import csv
from collections import Counter

# ──────────────────────────────────────────────────────────────
# Configuracao
# ──────────────────────────────────────────────────────────────
SRC_DIR = os.path.dirname(os.path.abspath(__file__))  # diretorio src/

FIELDNAMES = [
    'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente',
    'trofes_oponente', 'clan_oponente', 'resultado',
    'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
    'modo_jogo', 'tipo_batalha', 'arena',
    'deck_jogador', 'deck_oponente', 'vezes_enfrentado'
]

# Meses a consolidar: (prefixo_mes, nome_arquivo_mensal)
MESES = [
    ('202601', 'oponentes_mes_202601.csv'),
    ('202602', 'oponentes_mes_202602.csv'),
    ('202603', 'oponentes_mes_202603.csv'),
]


# ──────────────────────────────────────────────────────────────
# Utilitarios
# ──────────────────────────────────────────────────────────────
def _chave(row: dict) -> str:
    """Chave de deduplicacao: data + tag_oponente + modo_jogo."""
    return f"{row.get('data', '')}_{row.get('tag_oponente', '')}_{row.get('modo_jogo', '')}"


def _detect_delimiter(filepath: str) -> str:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        sample = f.read(2048)
    # Heuristica simples: mais ponto-e-virgulas que virgulas = ';'
    if sample.count(';') > sample.count(','):
        return ';'
    return ','


def _read_csv(filepath: str) -> list[dict]:
    """Le um CSV detectando delimitador e retorna lista de dicts."""
    if not os.path.exists(filepath):
        return []
    delim = _detect_delimiter(filepath)
    rows = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=delim)
        # Se o CSV nao tem header compativel, usa FIELDNAMES
        if reader.fieldnames and 'data' not in reader.fieldnames:
            f.seek(0)
            reader = csv.DictReader(f, delimiter=delim, fieldnames=FIELDNAMES)
        for row in reader:
            rows.append(dict(row))
    return rows


def _write_csv(filepath: str, rows: list[dict]):
    """Escreve um CSV com o cabecalho padrao e delimitador ';'."""
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore', delimiter=';')
        writer.writeheader()
        writer.writerows(rows)


def _recalculate_vezes_enfrentado(rows: list[dict]) -> list[dict]:
    """Recalcula vezes_enfrentado com base no total do conjunto de linhas."""
    counts = Counter(r.get('tag_oponente', '') for r in rows if r.get('tag_oponente'))
    for row in rows:
        tag = row.get('tag_oponente', '')
        row['vezes_enfrentado'] = counts.get(tag, 1)
    return rows


# ──────────────────────────────────────────────────────────────
# Logica principal
# ──────────────────────────────────────────────────────────────
def consolidar_mes(prefixo_mes: str, arquivo_mensal: str):
    """
    Une todos os CSVs diarios do mes (ex: oponentes_dia_202601*.csv)
    no arquivo mensal correspondente, sem duplicatas.
    """
    mensal_path = os.path.join(SRC_DIR, arquivo_mensal)

    # 1. Coleta todos os diarios do mes, ordenados por data
    prefix_dia = f"oponentes_dia_{prefixo_mes}"
    diarios = sorted([
        f for f in os.listdir(SRC_DIR)
        if f.startswith(prefix_dia) and f.endswith('.csv')
    ])

    if not diarios:
        print(f"  [AVISO] Nenhum arquivo diario encontrado para {prefixo_mes}.")
        return

    print(f"\n{'='*60}")
    print(f"  Consolidando {len(diarios)} diarios -> {arquivo_mensal}")
    print(f"{'='*60}")

    # 2. Le o mensal existente e monta conjunto de chaves
    mensal_rows = _read_csv(mensal_path)
    existing_keys = {_chave(r) for r in mensal_rows}
    print(f"  Mensal existente: {len(mensal_rows)} registros / {len(existing_keys)} chaves unicas")

    # 3. Le cada diario e adiciona apenas registros novos
    novos_total = 0
    diarios_processados = []

    for nome_diario in diarios:
        path_diario = os.path.join(SRC_DIR, nome_diario)
        rows_dia = _read_csv(path_diario)
        novos = 0
        for row in rows_dia:
            k = _chave(row)
            if k not in existing_keys:
                mensal_rows.append(row)
                existing_keys.add(k)
                novos += 1
        print(f"    {nome_diario}: {len(rows_dia)} linhas / {novos} novas adicionadas")
        novos_total += novos
        if rows_dia:  # so marca para remover se tinha dados validos
            diarios_processados.append(path_diario)

    print(f"\n  Total de novos registros adicionados: {novos_total}")

    # 4. Recalcula vezes_enfrentado no mensal completo
    mensal_rows = _recalculate_vezes_enfrentado(mensal_rows)

    # 5. Ordena por data desc (campo 'data' formato DD/MM/YYYY HH:MM)
    def parse_data(row):
        try:
            d = row.get('data', '')
            # formato: 21/04/2026 18:30
            parts = d.split(' ')
            dmy = parts[0].split('/')
            hm = parts[1].split(':') if len(parts) > 1 else ['00', '00']
            return (int(dmy[2]), int(dmy[1]), int(dmy[0]), int(hm[0]), int(hm[1]))
        except Exception:
            return (0, 0, 0, 0, 0)

    mensal_rows.sort(key=parse_data, reverse=True)

    # 6. Salva o mensal atualizado
    _write_csv(mensal_path, mensal_rows)
    print(f"  Mensal salvo: {arquivo_mensal} ({len(mensal_rows)} registros totais)")

    # 7. Remove os arquivos diarios consolidados
    print(f"\n  Removendo {len(diarios_processados)} arquivos diarios...")
    removidos = 0
    for path_diario in diarios_processados:
        os.remove(path_diario)
        print(f"    Removido: {os.path.basename(path_diario)}")
        removidos += 1
    print(f"  {removidos} arquivos removidos com sucesso.")


def main():
    print("\n" + "=" * 60)
    print("  CONSOLIDACAO: Diarios Jan/Fev/Mar 2026 -> Mensais")
    print("=" * 60)

    for prefixo, arquivo_mensal in MESES:
        consolidar_mes(prefixo, arquivo_mensal)

    print("\n" + "=" * 60)
    print("  CONSOLIDACAO CONCLUIDA!")
    print("  Verifique os arquivos mensais em: " + SRC_DIR)
    print("=" * 60 + "\n")


if __name__ == '__main__':
    main()
