import os
import json
import csv
from google import genai
from typing import List, Dict
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class GeminiDeckCoach:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            print("AVISO: GEMINI_API_KEY não encontrada, tentando GOOGLE_API_KEY...")
            self.api_key = os.environ.get("GOOGLE_API_KEY")
            
        if not self.api_key:
            print("ERRO: Nenhuma API Key encontrada.")
            self.client = None
        else:
            print(f"API Key encontrada: {self.api_key[:5]}...")
            # Força o uso da versão v1beta e ignora variáveis de ambiente automáticas do SDK
            from google.genai import Client
            self.client = Client(api_key=self.api_key, http_options={'api_version': 'v1beta'})
            
    def get_recent_battles_summary(self) -> str:
        # Pega o arquivo de batalhas mais recente
        base_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.join(base_dir, "data_csv_oficial")
        # Tenta o arquivo consolidado de 2026
        csv_file = os.path.join(base_path, "oponentes_ano_2026.csv")
        
        print(f"Lendo arquivo para IA: {csv_file}")
            
        summary = []
        try:
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                rows = list(reader)
                # Pega as últimas 10 batalhas
                recent = rows[-10:] if len(rows) > 10 else rows
                for r in recent:
                    summary.append(f"Modo: {r.get('modo_jogo')}, Res: {r.get('resultado')}, Deck Jogador: {r.get('deck_jogador')}, Elixir Vazado: {r.get('elixir_vazado_jogador', 0)}")
        except Exception as e:
            return f"Erro ao ler dados: {e}"
            
        return "\n".join(summary)

    def generate_coach_tips(self):
        if not self.client:
            return None
            
        data = self.get_recent_battles_summary()
        print(f"Dados coletados ({len(data)} chars)")
        if not data:
            print("AVISO: Nenhum dado de batalha encontrado para o Coach.")
            return None
            
        prompt = f"""
        Você é um treinador mestre de Clash Royale (Pro Coach).
        Analise o desempenho recente do jogador baseado nos dados abaixo e forneça 3 dicas estratégicas curtas e poderosas.
        
        Dados das últimas batalhas:
        {data}
        
        Sua resposta deve ser um JSON no formato:
        {{
            "tips": ["dica 1", "dica 2", "dica 3"],
            "deck_analysis": "breve análise do deck atual"
        }}
        
        Responda APENAS o JSON, sem markdown ou explicações extras.
        """
        
        print("Enviando requisição ao Gemini...")
        try:
            # Usando gemini-flash-latest que é estável localmente
            response = self.client.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt
            )
            print("Resposta recebida do Gemini.")
            # Limpa possíveis blocos de código markdown e trata thought_signature
            text = response.text
            # Limpeza robusta de blocos de codigo e espacos
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            text = text.strip()
            # Remover possivel virgula final antes de fechar array ou objeto
            import re
            text = re.sub(r',\s*([\]}])', r'\1', text)
            
            return json.loads(text)
        except Exception as e:
            print(f"Erro ao chamar Gemini: {e}")
            if hasattr(e, 'response'):
                print(f"Response error: {e.response}")
            return None

def main():
    coach = GeminiDeckCoach()
    tips = coach.generate_coach_tips()
    
    if tips:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(base_dir, "data_csv_oficial", "ai_coach_tips.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(tips, f, ensure_ascii=False, indent=4)
        print(f"Dicas do Coach geradas com sucesso: {output_path}")
    else:
        print("Falha ao gerar dicas do Coach.")

if __name__ == "__main__":
    main()
