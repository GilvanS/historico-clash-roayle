# Plano de Correção e Sanitização - Clash Royale Analytics Dashboard

> **Contexto**: O dashboard passou por uma atualização visual "Premium v2", mas houve uma regressão onde as batalhas sumiram do `index.html` e o modal de visualização de decks está desconfigurado (exibindo 4 itens por linha, o que achata as imagens).

## 🛠️ Objetivos Principais
1. **Sanitização**: Limpeza de arquivos residuais e pastas de configuração de outras IAs.
2. **Correção de Dados**: Restaurar a exibição das batalhas injetadas pelo `html_generator.py`.
3. **Ajuste de UI**: Corrigir o modal para exibir 2 batalhas/decks por linha, melhorando a visibilidade.
4. **Deploy Standard**: Garantir que o `index.html` seja gerado na pasta `/docs`.

---

## 📋 Task List (Passo a Passo)

### 1. [x] Sanitização do Ambiente
- [x] Remover pastas `.cursor`, `.zed`, `.trae`.
- [x] Deletar arquivos de log (`*.log`).
- [x] Deletar arquivos temporários e dumps de API (`temp_*.csv`, `api_full_dump.json`).

### 2. [/] Ajuste no Gerador Python (`src/html_generator.py`)
- [ ] Alterar o caminho de saída do `index.html` para `docs/index.html`.
- [ ] Verificar se as variáveis `battles_table_html` e `battles_cards_html` estão sendo populadas corretamente na função `generate_html_report`.
- [ ] Validar se as IDs das abas no Python coincidem com os seletores JS no `index.html`.

### 3. [/] Correção do Layout do Modal (CSS/JS)
- [ ] Localizar no CSS ou na injeção de HTML a classe responsável pelo grid do modal (provavelmente `.cr-vs-row-premium-v2` ou similar).
- [ ] Alterar para `grid-template-columns: repeat(2, 1fr)` para que apenas 2 batalhas apareçam por linha.
- [ ] Ajustar o tamanho das torres no modal para que não fiquem excessivamente grandes quando o layout for expandido.

---

## 🧠 Instruções para o Agente de Execução

### Regras de Ouro (MANDATÓRIO)
- **Idioma**: Responder sempre em Português do Brasil.
- **Logging**: Usar `@Log4j2` style. Mensagens de log **NUNCA** devem ter acentos (ex: `log.info("Validando exibicao")`).
- **Preservação**: Não apagar funções antigas que funcionavam (como a troca de abas). Apenas corrija o que foi quebrado no novo layout.
- **Naming**: Arquivos e classes devem manter nomes em Inglês.

### Guia de Edição do CSS (Modal)
Para garantir que o modal exiba apenas 2 itens por linha, use o seguinte padrão:
```css
.battle-modal-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr); /* Altera de 4 para 2 */
    gap: 20px;
    width: 100%;
}
```

### Verificação de Erro (Batalhas Sumidas)
Verifique no `index.html` se as seções `<div id="battles-content">` ou similares estão vazias. Se estiverem, o erro está na função `generate_full_html` dentro do `html_generator.py`, que não está encontrando a tag de substituição no template.
