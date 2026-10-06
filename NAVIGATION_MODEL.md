# Modelo de navegação (v0.16.0)

## Estado honesto

**O que existe hoje:** uma barra lateral fixa de 248 px (`.shell { grid-template-columns: 248px 1fr }`), com lista
**plana** de até 36 itens, que vira gaveta deslizante abaixo de 980 px. Funciona, é acessível (há `skip link`,
`aria-current`, `aria-expanded`), e **não** é o que foi pedido.

**O que foi pedido, verbatim, em rodada anterior:**

> "prefiro menus suspensos retráteis selecionáveis horizontais"
> "uma grande área de trabalho ao invés de menus laterais"

**Classificação honesta: AMARELO.** A preferência de navegação continua **não atendida**. Não foi atendida nesta
rodada por decisão explícita — o pedido desta vez abre com "eu não mandaria o Manus começar pelo visual" e manda a
sequência de 13 passos que coloca Design System e UX/UI **depois** da reconstrução de domínio. Mudar a navegação
agora, com a AI ainda crescendo 26 telas, seria refazer duas vezes.

**Portanto isto é entrega de design, não de engenharia, e está aqui especificada para o designer executar.**

## O modelo proposto

Horizontal, em dois níveis, com área de trabalho larga:

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  Impacto    [ Identidade ▾ ][ Oportunidades ▾ ][ Rede ▾ ][ Negociação ▾ ]     │
│             [ Execução ▾ ][ Resultado ▾ ]            🔔 3   [Organização ▾]   │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ← área de trabalho inteira, sem trilho lateral permanente →                 │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

Seis grupos suspensos (os sete domínios de `INFORMATION_ARCHITECTURE.md`, com Administração recolhida no seletor de
organização). Cada grupo abre e fecha; nenhum consome largura quando fechado.

Regras do modelo:

1. **Os grupos vêm do backend.** `GET /v1/workspace` já devolve `sections` **na ordem** que a persona precisa e
   `capabilities` dizendo o que ela pode. O menu deve ser montado a partir disso, não de uma constante no frontend
   (hoje é `NAV` em `app.tsx` — seis listas mantidas à mão, uma por tipo de organização, que é exatamente a fonte de
   divergência a eliminar).
2. **Área de trabalho em primeiro lugar.** `/area` (o workspace) é o destino de `/`, não um item entre trinta e seis.
3. **Nada de item que a pessoa não pode usar.** `capabilities` resolve: item sem capacidade não aparece; se aparecer
   por ser parte do plano superior, diz o que exige e quanto custa.
4. **Máximo de sete itens por grupo suspenso.** Se um grupo passar de sete, ele tem um subgrupo mal resolvido — o que
   acontece hoje com Execução.
5. **Um só caminho por tela.** Hoje "Prontidão" e "Prontidão por finalidade" são dois itens de topo; devem ser uma
   tela com duas abas.
6. **Mobile não é o mesmo menu encolhido.** Abaixo de 760 px: barra inferior com cinco destinos fixos (Área de
   trabalho · Marketplace · Propostas · Conversas · Mais) e a árvore completa dentro de "Mais". Ver
   `MOBILE_READINESS_FINAL.md`.

## Mapeamento completo: item de hoje → grupo proposto

| Grupo | Itens (OSC, como exemplo mais carregado) |
|---|---|
| **Identidade** | Instituição · Diagnóstico · Perfil público · Experiências declaradas · Verificação pública · Conquistas |
| **Oportunidades** | Marketplace · Meus anúncios · Oportunidades · Ideias · Editais |
| **Rede** | Relações · Conversas · Atividade da rede · Profissionais parceiros |
| **Negociação** | Propostas · Candidaturas · Acordos · Rascunhos |
| **Execução** | Projetos · Prontidão *(com aba "por finalidade")* · Documentos *(com aba "montagem")* · Campanha · Cotas |
| **Resultado** | Relatórios de impacto · Relatórios · Mapa · Biblioteca de soluções · Materiais |
| **(seletor de organização)** | Equipe · Pagamentos · Vocabulário · Sair |

36 itens → 6 grupos com no máximo 6 itens visíveis cada, mais duas consolidações em abas.

## O que **não** deve mudar

* As URLs. Cada uma das 145 telas tem endereço estável; mudar endereço quebra link compartilhado, aviso por e-mail e
  o destino que a recomendação devolve (`recommendation.LINKS`). Há teste de arquitetura —
  `test_recommendation_links_exist_in_the_app` — que falha se um destino deixar de existir. **O designer pode
  reagrupar o menu sem tocar em URL.**
* O `skip link`, o `aria-current="page"` e o `aria-expanded` do botão de menu. São o piso de acessibilidade já
  conquistado.
* O seletor de organização ativa: pessoas com mais de uma organização trocam por ali, e a troca recarrega a sessão.

## Navegação pública

Separada e mínima, porque atende quem não tem conta: vitrine · marketplace publicado · `impacto.app/@identificador` ·
verificação pública · entrar. **Nenhum** item privado aparece aqui, e o cabeçalho público não é o mesmo componente do
cabeçalho autenticado — misturar os dois é como um link privado vaza para uma página pública.
