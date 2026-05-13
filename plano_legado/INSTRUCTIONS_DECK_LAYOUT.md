# Instruções para Correção de Layout: Exibição de Decks (2 Colunas)

Este documento contém o plano técnico e a lista de tarefas para refatorar o layout de decks do Dashboard Clash Royale, otimizando a visualização para o padrão **Premium v2**.

---

## 🎯 Objetivo
Ajustar a exibição dos decks nas abas de Performance e Spy de Guerra de **4 colunas para 2 colunas** por linha, melhorando a legibilidade das métricas e o respiro visual.

## 🛠️ Plano de Implementação

### 1. Localização do Alvo
- **Arquivo**: `src/html_generator.py`
- **Método**: `get_base_css_styles()`
- **Seletor CSS**: `.cr-decks-list`

### 2. Mudanças no Grid CSS
Atualmente, o grid pode estar configurado com `auto-fill` ou um número excessivo de colunas. A nova configuração deve forçar o layout de duas colunas em desktops.

**Código Sugerido:**
```css
/* Localize e substitua a classe .cr-decks-list */
.cr-decks-list {
    display: grid;
    grid-template-columns: repeat(2, 1fr) !important; /* Força 2 colunas */
    gap: 25px;
    padding: 15px;
    width: 100%;
}

/* Garanta a responsividade para dispositivos móveis */
@media (max-width: 1000px) {
    .cr-decks-list {
        grid-template-columns: 1fr !important; /* 1 coluna em telas menores */
    }
}
```

### 3. Ajuste de Cards
- Verifique a classe `.cr-deck-card`.
- Remova qualquer `max-width` que limite o card a menos de 45% da largura do container.
- Garanta que o card preencha o espaço da coluna do grid (`width: 100%`).

---

## ✅ Task Checklist

- [ ] Abrir `src/html_generator.py`.
- [ ] Localizar a definição de `.cr-decks-list` dentro de `get_base_css_styles()`.
- [ ] Aplicar `grid-template-columns: repeat(2, 1fr)`.
- [ ] Adicionar/Atualizar a Media Query para `@media (max-width: 1000px)`.
- [ ] Salvar o arquivo e executar `python src/html_generator.py` localmente.
- [ ] Validar no arquivo `index.html` gerado se as abas "Meus Decks da Semana" e "Melhores Decks" agora exibem 2 itens por linha.

---

## ⚠️ Regras Obrigatórias (Diretrizes Globais)

1.  **Preservação Visual**: Não altere cores, transparências ou efeitos de Glassmorphism. O foco é estritamente estrutural (layout).
2.  **Clean Code**: Mantenha a indentação correta dentro das f-strings do Python.
3.  **SOLID**: Não altere a lógica de processamento de dados, apenas a camada de apresentação (CSS).
4.  **Logging**: Se houver necessidade de log, use o padrão do projeto: `log.info("Mensagem sem acentos")` com a anotação `@Log4j2`.

---
*Documento gerado por Antigravity para suporte a múltiplos agentes.*
