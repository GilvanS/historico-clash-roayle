# Instruções para Extração Manual de Batalhas (Clash Royale API)

Este documento contém os códigos e comandos necessários para realizar a extração manual das suas batalhas e atualizar o histórico oficial de 2026.

## 1. Código Python para Execução

O script principal para esta tarefa é o `src/force_import_2026.py`. Ele realiza as seguintes ações:
- Carrega o histórico existente do CSV oficial.
- Consulta as últimas 25-30 batalhas diretamente da API.
- Realiza o merge inteligente (evitando duplicatas).
- Regera o arquivo `oponentes_ano_2026.csv` com todo o histórico consolidado.

### Como executar via Terminal:

```powershell
# Acesse a pasta do código-fonte
cd src

# Execute o script de importação forçada
python force_import_2026.py
```

---

## 2. Comandos PowerShell Úteis

Para facilitar a automação ou verificação, você pode usar os seguintes comandos no PowerShell:

### Configurar Token e Executar (Caso não use variáveis de ambiente):
```powershell
$env:CR_API_TOKEN = "SEU_TOKEN_AQUI"
$env:CR_PLAYER_TAG = "#2QR292P"
cd src
python force_import_2026.py
```

### Verificar Contagem de Batalhas no CSV:
```powershell
Get-Content src/data_csv_oficial/oponentes_ano_2026.csv | Measure-Object -Line
```

### Buscar uma Batalha Específica no Histórico:
```powershell
Select-String -Path src/data_csv_oficial/oponentes_ano_2026.csv -Pattern "NomeDoOponente"
```

---

## 3. Busca por Data Específica (Pesquisa)

Caso precise apenas consultar batalhas de um dia específico sem atualizar o arquivo oficial, use o script de busca:

```powershell
cd src/scratch
python search_battles_by_date.py
```
*(Nota: Este script solicitará a data desejada no formato DD/MM/YYYY)*

---

## 4. Notas Técnicas (Impedindo Erros)

- **Encoding**: O script `force_import_2026.py` já está configurado para lidar com emojis em nomes de jogadores no Windows, evitando erros de `UnicodeEncodeError`.
- **Merge**: O sistema usa o `battleTime` e a `tag_oponente` como chave única. Se você rodar o script várias vezes, ele não duplicará as mesmas batalhas no seu CSV.
- **Sincronização**: Após rodar o script localmente, lembre-se de fazer o `git push` para que o Dashboard Web seja atualizado via GitHub Actions.

```powershell
git add .
git commit -m "update: atualização manual de batalhas via script"
git push origin main
```
