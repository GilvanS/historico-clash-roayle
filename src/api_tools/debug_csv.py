
import os

path = 'a:/Workspace/historico-clash-roayle/src/data_csv_oficial/oponentes_ano_2026.csv'
if os.path.exists(path):
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        content = f.read()
    nulls = content.count(b'\x00')
    print(f"File: {path}")
    print(f"Size: {size} bytes")
    print(f"Null bytes: {nulls}")
    
    # Check for other weird stuff
    lines = content.splitlines()
    print(f"Total lines (binary split): {len(lines)}")
    
    # Check first 5 lines decoded
    print("\nFirst 5 lines (decoded if possible):")
    for i, line in enumerate(lines[:5]):
        try:
            print(f"{i}: {line.decode('utf-8')}")
        except:
            print(f"{i}: [Binary Data: {line[:50]}]")
else:
    print(f"File not found: {path}")
