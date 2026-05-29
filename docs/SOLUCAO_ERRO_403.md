# Solucao para Erro 403 - Invalid IP

## Problema

O erro `403 Forbidden` com a mensagem `"API key does not allow access from IP"` significa que seu token da API foi criado com restricao de IP, mas voce esta tentando acessar de um IP diferente.

## Solucoes

### Opcao 1: Atualizar o Token para Permitir seu IP Atual (Recomendado)

1. Acesse: https://developer.clashroyale.com
2. Va em "My Keys" ou "Keys"
3. Encontre seu token atual
4. Clique em "Edit" ou "Update"
5. Na secao "IP Whitelist" ou "CIDR", adicione seu IP atual:
   - Seu IP atual: `45.79.218.79`
   - Ou remova a restricao de IP (menos seguro, mas funciona de qualquer lugar)

### Opcao 2: Criar um Novo Token sem Restricao de IP

1. Acesse: https://developer.clashroyale.com
2. Va em "My Keys" → "Create New Key"
3. **NAO adicione nenhum IP na whitelist** (deixe em branco)
4. Copie o novo token
5. Use o novo token no script

### Opcao 3: Usar o Token de um Local com IP Permitido

Se voce tem acesso a um servidor ou rede com o IP `189.201.250.94`, pode executar o script de la.

## Como Descobrir seu IP Atual

Voce pode verificar seu IP atual em:
- https://whatismyipaddress.com
- https://ipinfo.io

## Apos Atualizar o Token

Depois de atualizar o token, execute novamente:

```powershell
cd src
$env:CR_API_TOKEN="seu_novo_token_aqui"
$env:CR_PLAYER_TAG="#2QR292P"
python opponents_report.py
```

## Nota de Seguranca

- **Com restricao de IP**: Mais seguro, mas so funciona do IP configurado
- **Sem restricao de IP**: Funciona de qualquer lugar, mas menos seguro se o token vazar

Para uso pessoal, geralmente e seguro remover a restricao de IP.

