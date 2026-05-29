import sys
import os
import logging

# Adiciona o diretório src ao path
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.append(src_dir)

from html_generator import GitHubPagesHTMLGenerator

def verify():
    # Setup logging to see output
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("Iniciando verificacao do gerador HTML...")
    
    try:
        generator = GitHubPagesHTMLGenerator()
        # Simula a geracao sem precisar de tokens reais (o gerador deve ler os CSVs locais)
        html_content = generator.generate_html_report()
        
        output_path = os.path.join(os.path.dirname(__file__), 'test_index.html')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        logger.info(f"HTML gerado com sucesso em: {output_path}")
        logger.info(f"Tamanho do arquivo: {len(html_content)} bytes")
        
    except Exception as e:
        logger.error(f"Erro durante a geracao do HTML: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    verify()
