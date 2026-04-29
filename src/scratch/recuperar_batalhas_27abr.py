#!/usr/bin/env python3
"""
Script de recuperacao emergencial das batalhas do dia 27/04/2026.
Consulta a API agora e verifica quais batalhas do dia 27 ainda estao visiveis,
em seguida faz merge com o CSV existente sem duplicar.
"""
import os
import sys
import io
import csv
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from opponents_report import OpponentsReporter

TOKEN = os.getenv("CR_API_TOKEN", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjkwODQxMGZlLTdiNjgtNGI1Ny04YWU5LWVhMTE2YWZiODMxYyIsImlhdCI6MTc2NTQ5Mzk4OSwic3ViIjoiZGV2ZWxvcGVyLzllZjZlMmQ2LTQ1ZmEtYjdkMi1jZGI2LTZmYWJmODA0NWFiZiIsInNjb3BlcyI6WyJyb3lhbGUiXSwibGltaXRzIjpbeyJ0aWVyIjoiZGV2ZWxvcGVyL3NpbHZlciIsInR5cGUiOiJ0aHJvdHRsaW5nIn0seyJjaWRycyI6WyI0NS43OS4yMTguNzkiXSwidHlwZSI6ImNsaWVudCJ9XX0.pDhAHyZ2tAR5dg2QwBXabKTryUvaT7N9QxFKDUSrvZ_1P99x3hLP1oXy49Y9E4a4Ty_TiiUgqd5BTYzwO1Z3wA")
TAG = os.getenv("CR_PLAYER_TAG", "#2QR292P")

TARGET_DATE_BRT = "27/04/2026"

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                        "data_csv_oficial")
DIA_CSV = os.path.join(DATA_DIR, "oponentes_dia_20260427.csv")
ANO_CSV = os.path.join(DATA_DIR, "oponentes_ano_2026.csv")

print("=" * 60)
print(f"RECUPERACAO EMERGENCIAL - batalhas de {TARGET_DATE_BRT}")
print("=" * 60)

# 1. Conecta e busca battle log da API agora
print(f"\n[1] Consultando API para tag {TAG}...")
reporter = OpponentsReporter(TOKEN)
battles = reporter.get_battle_log(TAG)

if not battles:
    print("ERRO: Nao foi possivel obter batalhas da API.")
    sys.exit(1)

print(f"    API retornou {len(battles)} batalhas no total.")

# 2. Filtra APENAS as do dia 27/04/2026 (em BRT)
battles_27 = []
for b in battles:
    bt = b.get('battleTime', '')
    if len(bt) >= 15:
        try:
            dt_utc = datetime.strptime(bt[:15], '%Y%m%dT%H%M%S')
            dt_brt = dt_utc - timedelta(hours=3)
            if dt_brt.strftime('%d/%m/%Y') == TARGET_DATE_BRT:
                battles_27.append((dt_brt, b))
        except Exception:
            continue

battles_27.sort(key=lambda x: x[0], reverse=True)

print(f"\n[2] Batalhas do dia {TARGET_DATE_BRT} encontradas na API AGORA: {len(battles_27)}")
for dt_brt, b in battles_27:
    opponents = b.get('opponent', [])
    opp_name = opponents[0].get('name', '?') if opponents else '?'
    print(f"    {dt_brt.strftime('%H:%M')} BRT | {opp_name}")

if not battles_27:
    print("\n[AVISO] Nenhuma batalha do dia 27/04 esta mais visivel na API.")
    print("        Infelizmente os dados foram perdidos — a janela da API foi superada.")
    sys.exit(0)

# 3. Carrega chaves ja existentes no CSV do dia para evitar duplicatas
existing_keys = set()
if os.path.exists(DIA_CSV):
    with open(DIA_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Chave: data + tag_oponente
            key = (row.get('data', '').strip(), row.get('tag_oponente', '').strip())
            existing_keys.add(key)
    print(f"\n[3] CSV do dia 27 ja tem {len(existing_keys)} registro(s). Verificando duplicatas...")
else:
    print(f"\n[3] Arquivo {DIA_CSV} nao existe. Sera criado do zero.")

# 4. Extrai e filtra batalhas novas
novas_batalhas = []
for dt_brt, b in battles_27:
    info = reporter.extract_opponent_info(b, TAG)
    if not info:
        continue

    teams = b.get('team', [])
    player_team = next((t for t in teams if t.get('tag') == TAG), None)
    deck_jogador = reporter.format_deck(player_team.get('cards', [])) if player_team else ''

    opponents = b.get('opponent', [])
    opp_team = opponents[0] if opponents else None
    deck_oponente = reporter.format_deck(opp_team.get('cards', [])) if opp_team else ''

    data_fmt = dt_brt.strftime('%d/%m/%Y %H:%M')
    tag_oponente = info.get('tag_oponente', '')
    key = (data_fmt, tag_oponente)

    if key in existing_keys:
        print(f"    [JA EXISTE] {data_fmt} | {info.get('nome_oponente','?')}")
        continue

    novas_batalhas.append({
        'data': data_fmt,
        'nome_oponente': info.get('nome_oponente', ''),
        'tag_oponente': tag_oponente,
        'nivel_oponente': info.get('nivel_oponente', 0),
        'trofes_oponente': info.get('trofes_oponente', 0),
        'clan_oponente': info.get('clan_oponente', 'Sem cla'),
        'resultado': info.get('resultado', ''),
        'coroas_jogador': info.get('coroas_jogador', 0),
        'coroas_oponente': info.get('coroas_oponente', 0),
        'mudanca_trofes': info.get('mudanca_trofes', 0),
        'modo_jogo': info.get('modo_jogo', ''),
        'tipo_batalha': info.get('tipo_batalha', ''),
        'arena': info.get('arena', ''),
        'deck_jogador': deck_jogador,
        'deck_oponente': deck_oponente,
        'vezes_enfrentado': 1
    })
    print(f"    [NOVA] {data_fmt} | {info.get('nome_oponente','?')} | {info.get('resultado','')}")

print(f"\n[4] Batalhas NOVAS para adicionar: {len(novas_batalhas)}")

if not novas_batalhas:
    print("    Nenhuma batalha nova encontrada. CSV ja esta atualizado.")
    sys.exit(0)

# 5. Lê o conteudo atual do CSV do dia (se existir) e adiciona as novas
fieldnames = [
    'data', 'nome_oponente', 'tag_oponente', 'nivel_oponente',
    'trofes_oponente', 'clan_oponente', 'resultado',
    'coroas_jogador', 'coroas_oponente', 'mudanca_trofes',
    'modo_jogo', 'tipo_batalha', 'arena', 'deck_jogador', 'deck_oponente', 'vezes_enfrentado'
]

linhas_existentes = []
if os.path.exists(DIA_CSV):
    with open(DIA_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        linhas_existentes = list(reader)

todas = linhas_existentes + novas_batalhas
# Ordena por data (mais recente primeiro)
todas.sort(key=lambda r: r.get('data', ''), reverse=True)

with open(DIA_CSV, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(todas)

print(f"\n[5] CSV do dia 27 atualizado: {DIA_CSV}")
print(f"    Total de registros agora: {len(todas)} ({len(linhas_existentes)} anteriores + {len(novas_batalhas)} novas)")

# 6. Tambem adiciona no CSV anual para consistencia
print(f"\n[6] Atualizando CSV anual: {ANO_CSV}")
linhas_ano = []
if os.path.exists(ANO_CSV):
    with open(ANO_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        linhas_ano = list(reader)

# Chaves do CSV anual
existing_keys_ano = set(
    (r.get('data', '').strip(), r.get('tag_oponente', '').strip())
    for r in linhas_ano
)

novas_para_ano = [
    b for b in novas_batalhas
    if (b['data'], b['tag_oponente']) not in existing_keys_ano
]

if novas_para_ano:
    todas_ano = linhas_ano + novas_para_ano
    todas_ano.sort(key=lambda r: r.get('data', ''), reverse=True)
    with open(ANO_CSV, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(todas_ano)
    print(f"    CSV anual atualizado: {len(novas_para_ano)} linha(s) adicionada(s). Total: {len(todas_ano)}")
else:
    print("    Nenhuma linha nova para o CSV anual.")

print("\n" + "=" * 60)
print("RECUPERACAO CONCLUIDA COM SUCESSO!")
print("=" * 60)
