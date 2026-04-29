with open('docs/index.html', 'r', encoding='utf-8') as f:
    text = f.read()
    import re
    matches = re.findall(r'function filter.*?\{', text, re.DOTALL)
    print('Filter functions:', matches)
    
    bars = re.findall(r'onclick=[\"\'](.*?)[\"\']', text)
    print('Onclick handlers:', set([b for b in bars if 'filter' in b.lower()]))
