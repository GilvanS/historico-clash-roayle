# Como Habilitar GitHub Pages

Voce tem duas opcoes para habilitar o GitHub Pages:

## Opcao 1: Via Script Python (Automatico)

1. **Crie um GitHub Personal Access Token:**
   - Vá para: https://github.com/settings/tokens
   - Clique em "Generate new token (classic)"
   - Dê um nome (ex: "Enable Pages")
   - Selecione o escopo `repo` (acesso completo aos repositorios)
   - Clique em "Generate token"
   - **COPIE O TOKEN** (voce so vera ele uma vez!)

2. **Execute o script:**
   ```bash
   # Windows PowerShell
   $env:GITHUB_TOKEN="seu_token_aqui"
   python habilitar_github_pages.py
   
   # Ou passe o token diretamente
   python habilitar_github_pages.py --token "seu_token_aqui"
   ```

## Opcao 2: Manual (Mais Simples)

1. **Acesse as configuracoes do repositorio:**
   - Vá para: https://github.com/GilvanS/clash-royale-history/settings/pages

2. **Configure a fonte:**
   - Na secao "Source", selecione **"GitHub Actions"**
   - Clique em **"Save"**

3. **Pronto!**
   - O GitHub Pages estara habilitado
   - O proximo workflow automaticamente fara o deploy
   - Ou execute manualmente na aba "Actions"

## Verificacao

Apos habilitar, o dashboard estara disponivel em:
- **https://gilvans.github.io/clash-royale-history/**

## Nota Importante

- O workflow continuara funcionando mesmo sem GitHub Pages habilitado
- Todos os dados continuarao sendo coletados e salvos
- O README continuara sendo atualizado
- Apenas o deploy para o site publico nao funcionara ate habilitar

## Tempo de Espera

Apos habilitar, pode levar alguns minutos para:
- O primeiro deploy ser processado
- O site ficar disponivel publicamente

