import os
import sys
from dotenv import load_dotenv

# Adiciona src ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Tenta carregar de dois lugares
print(f"Diretorio atual: {os.getcwd()}")
print(f"Arquivo .env na raiz existe? {os.path.exists('../.env')}")
print(f"Arquivo .env em src existe? {os.path.exists('.env')}")

# Carrega explicitamente da raiz (um nível acima de src)
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path)

tag_pri = os.getenv('CR_PLAYER_TAG')
tag_sec = os.getenv('CR_PLAYER_TAG_SEC')

print(f"CR_PLAYER_TAG: {tag_pri}")
print(f"CR_PLAYER_TAG_SEC: {tag_sec}")

from html_generator import GitHubPagesHTMLGenerator
gen = GitHubPagesHTMLGenerator()
print(f"Generator tracked_tags: {gen.tracked_tags}")
