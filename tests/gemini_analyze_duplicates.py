import os
import csv
from google import genai
from datetime import datetime

def analyze_with_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Erro: GEMINI_API_KEY não encontrada.")
        return

    client = genai.Client(api_key=api_key)
    
    # Carrega os dados dos CSVs recentes para análise
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, '..', 'data', 'csv')
    
    files_to_analyze = [
        'oponentes_dia_20260428.csv',
        'oponentes_dia_20260429.csv'
    ]
    
    combined_data = ""
    for filename in files_to_analyze:
        path = os.path.join(data_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                combined_data += f"\n--- Arquivo: {filename} ---\n{content}\n"

    if not combined_data:
        print("Nenhum dado encontrado para analisar.")
        return

    prompt = f"""
    Você é um especialista em análise de dados de Clash Royale. 
    Abaixo estão os dados de batalhas recentes em formato CSV.
    
    O usuário suspeita que existam DUPLICATAS ou ANOMALIAS baseadas em horários próximos, 
    mesmo que os campos não sejam 100% idênticos (fuso horário, delays de API, etc).
    
    Analise os dados abaixo e identifique:
    1. Partidas que parecem ser a mesma (mesmo oponente, mesmo resultado, coroas e troféus próximos) mas com horários diferentes.
    2. Qualquer inconsistência estranha nos dados.
    
    Dados:
    {combined_data}
    
    Responda em Português do Brasil com uma lista clara das suspeitas.
    """

    print("Enviando dados para o Gemini para análise profunda...")
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt
    )
    
    print("\n=== ANÁLISE DO GEMINI ===")
    print("\nAnálise concluída. Salvando em anomalies_report.md...")
    
    # Salva a análise em um arquivo para o usuário ver
    report_path = os.path.join(base_dir, 'anomalies_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# Relatório de Anomalias (Gerado por AI)\n\nData: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")
        f.write(response.text)
    print(f"Relatório salvo com sucesso em: {report_path}")

if __name__ == "__main__":
    analyze_with_gemini()
