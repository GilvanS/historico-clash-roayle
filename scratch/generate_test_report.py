
import os
import sys

# Add src to path
sys.path.append(os.path.abspath('src'))
from html_generator import GitHubPagesHTMLGenerator

def generate_test_report():
    print("Iniciando geracao de relatorio de teste...")
    generator = GitHubPagesHTMLGenerator()
    
    # Gerar o relatório completo
    html_content = generator.generate_html_report()
    
    output_path = 'scratch/test_report.html'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Relatorio gerado em: {output_path}")
    print(f"Tamanho do arquivo: {os.path.getsize(output_path)} bytes")

if __name__ == "__main__":
    generate_test_report()
