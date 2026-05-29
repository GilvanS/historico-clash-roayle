import requests
import os
import json

def test_battle_log():
    api_key = os.getenv('CR_API_TOKEN')
    player_tag = "%232B2Y0R80"
    url = f"https://api.clashroyale.com/v1/players/{player_tag}/battlelog"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json'
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        log = response.json()
        if log:
            print(json.dumps(log[0], indent=2))
        else:
            print("Log vazio")
    else:
        print(f"Erro: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_battle_log()
