# Como Atualizar o Token com o IP Correto

## Problema Atual

Seu token esta configurado para o IP: `189.201.251.216`
Mas sua requisicao esta vindo do IP: `45.79.218.79`

## Solução: Usar o arquivo .env (Seguro e Permanente)

A melhor forma de gerenciar seu token e tag agora é através do arquivo `.env` localizado na raiz do projeto.

1. Abra o arquivo `.env` na raiz do projeto.
2. Adicione ou atualize as seguintes linhas:
   ```env
   CR_API_TOKEN="seu_novo_token_aqui"
   CR_PLAYER_TAG="#2QR292P"
   ```
3. Salve o arquivo.

## Como obter o IP para o Token

Seu IP atual é: **45.79.218.79** (ou verifique em https://ipinfo.io)

1. Acesse: https://developer.clashroyale.com
2. Edite sua chave e adicione este IP na whitelist.

## Após Atualizar

Basta executar o script normalmente. Ele carregará automaticamente as configurações do arquivo `.env`:

```powershell
cd src
python legacy/opponents_report.py
```

## Dica

Se seu IP muda frequentemente (ISP dinamico), e melhor criar um token **sem restricao de IP** para uso pessoal.

