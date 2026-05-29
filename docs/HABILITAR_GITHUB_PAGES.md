# Como Habilitar GitHub Pages

O workflow de analytics tenta fazer deploy automatico para o GitHub Pages, mas ele precisa estar habilitado primeiro.

## Passos para Habilitar

1. **Acesse as configurações do repositório:**
   - Vá para: `https://github.com/GilvanS/clash-royale-history/settings/pages`

2. **Configure a fonte:**
   - Na secao "Source", selecione **"GitHub Actions"**
   - Clique em **"Save"**

3. **Aguarde o proximo workflow:**
   - O workflow `Update Clash Royale Analytics` executara automaticamente
   - Ou voce pode executar manualmente na aba "Actions"

## Verificacao

Apos habilitar, o dashboard estara disponivel em:
- `https://gilvans.github.io/clash-royale-history/`

## Nota

- O workflow continuara funcionando mesmo se o GitHub Pages nao estiver habilitado
- Apenas o deploy falhara (mas nao quebrara o workflow)
- Todos os dados continuarao sendo coletados e salvos no repositorio

