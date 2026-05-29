with open('src/html_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Procura todas as ocorrencias e imprime o contexto ao redor
import re
matches = [m.start() for m in re.finditer('generate_global_scripts', content)]
for idx, pos in enumerate(matches):
    start = max(0, pos - 150)
    end = min(len(content), pos + 150)
    context = content[start:end].replace('\n', ' ').replace('\r', '')
    print(f"Match {idx+1}: ... {context} ...")
