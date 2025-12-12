# Como Atualizar o Token com o IP Correto

## Problema Atual

Seu token esta configurado para o IP: `189.201.251.216`
Mas sua requisicao esta vindo do IP: `45.79.218.79`

## Solucao: Adicionar o IP Atual

1. Acesse: https://developer.clashroyale.com
2. Va em "My Keys" ou "Keys"
3. Encontre seu token e clique em "Edit" ou "Update"
4. Na secao "IP Whitelist" ou "CIDR", adicione:
   - **IP atual**: `45.79.218.79`
   - Ou mantenha ambos: `189.201.251.216` E `45.79.218.79`

## Solucao Alternativa: Remover Restricao de IP (Mais Facil)

1. Acesse: https://developer.clashroyale.com
2. Va em "My Keys" → "Create New Key"
3. **NAO adicione nenhum IP** (deixe a whitelist vazia)
4. Copie o novo token
5. Use o novo token

## Verificar seu IP Atual

Seu IP atual e: **45.79.218.79**

Voce pode verificar em:
- https://whatismyipaddress.com
- https://ipinfo.io

## Apos Atualizar

Execute novamente:

```powershell
cd src
$env:CR_API_TOKEN="seu_token_atualizado"
$env:CR_PLAYER_TAG="#2QR292P"
python opponents_report.py
```

## Dica

Se seu IP muda frequentemente (ISP dinamico), e melhor criar um token **sem restricao de IP** para uso pessoal.

