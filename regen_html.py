#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.html_generator import GitHubPagesHTMLGenerator

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

gen = GitHubPagesHTMLGenerator()
html = gen.generate_html_report()
output_path = os.path.join(os.path.dirname(__file__), 'index.html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"HTML generated: {len(html)} bytes")