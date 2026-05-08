import re, requests
import urllib3
urllib3.disable_warnings()
with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()
urls = set(re.findall(r'src=\"(https://[^\"]+\.png)\"', content))
broken = []
for u in urls:
    try:
        if requests.head(u, verify=False).status_code != 200:
            broken.append(u)
    except:
        broken.append(u)
print('Broken URLs:', broken)
