# Guia de quem vai testar

Para a pessoa que recebeu um acesso e vai procurar defeito. Lê-se em dez minutos; o resto é consulta.

> **O que já se sabe que está quebrado ou ausente não é defeito novo.** A seção 6 lista isso. Relatar
> de novo custa o tempo de quem lê. Relatar o que **não** está lá é o que vale.

---

## 1. Antes da primeira tela

Você precisa de três coisas de quem te deu o acesso:

1. **A URL** e a confirmação de que é **staging** — nunca teste em produção.
2. **Um usuário e uma organização**, com o **tipo** dito: OSC, Empresa, Governo, Apoiador,
   Profissional ou Administração. O tipo decide o que você enxerga; sem saber o seu, metade das telas
   "sumidas" é comportamento correto.
3. **Se há segundo fator** na sua conta. Se houver, tenha o aplicativo autenticador à mão antes de
   começar — algumas rotas exigem reautenticação no meio do caminho.

## 2. Os seis tipos, e por que isso importa mais que parece

A mesma rota se comporta diferente conforme o tipo da sua organização. `/editais` é "Programas" para
Empresa e "Editais" para Governo. 37 telas só existem para Administração. **Ver "não encontrado" não
é necessariamente defeito** — pode ser a regra de tipo funcionando.

Antes de relatar "tela sumiu", confirme no painel de telas se o seu tipo alcança aquela rota.

## 3. O painel de telas

O painel navegável lista as **218 telas** que o roteador serve, com rota, componente, arquivo,
quais tipos alcançam, se está em algum menu e quais operações de API o componente chama. É gerado
direto do código (`scripts/make_screen_inventory.py` e `scripts/make_screen_backend_map.py`), então
não há tela esquecida nem tela inventada.

Use-o de três maneiras:

- **Para achar o que testar.** Filtre por tipo e percorra. 119 telas não estão em menu nenhum: você
  só chega nelas por link direto, digitando a rota.
- **Para saber o que esperar.** "sem chamada direta" (60 telas): o componente não chama a API por
  conta própria — pode ser tela estática ou pode buscar por um auxiliar compartilhado. Tela vazia ali
  é menos suspeita que tela vazia numa que chama seis operações.
- **Para registrar o que achou.** Cada tela aceita uma marcação — **verde** (aprovada), **amarelo**
  (ajustar), **vermelho** (bloqueada) — e uma nota. Fica salvo para quem abrir depois, inclusive para
  quem for corrigir.

**52 telas exigem um registro existente** (a rota tem `:id`). Elas não abrem sozinhas: chegue nelas
clicando a partir da lista correspondente, não digitando a rota.

## 4. O que procurar, em ordem de utilidade

1. **Dado de outra organização aparecendo no seu lugar.** É o defeito mais grave possível aqui. Se
   acontecer, pare de testar e relate imediatamente com a URL e a hora.
2. **Botão que não faz nada.** Clique e observe: apareceu mensagem de erro? Nada? Mensagem de
   sucesso sem mudança na tela? "Sucesso sem efeito" é pior que erro visível e é o que mais escapa.
3. **Número que não bate** entre duas telas que falam da mesma coisa (uma lista e um painel, por
   exemplo).
4. **Texto que promete o que não acontece.** Rótulo dizendo "enviado" quando nada foi enviado.
5. **Formulário que aceita o que não devia** (data no passado, valor negativo, CNPJ inválido) ou que
   recusa o que devia aceitar.
6. **Tela que quebra em telefone.** Rolagem horizontal, texto cortado, botão fora do alcance.
7. **Navegação por teclado.** Percorra com Tab: dá para ver onde está o foco? Dá para acionar tudo
   sem o mouse?

## 5. Como relatar

Um relato útil tem cinco linhas e nada mais:

```
Rota:        /projetos/9f3c…/indicadores
Tipo:        OSC
O que fiz:   cliquei em "Registrar medição" com valor 12 e data de ontem
O que vi:    "Medição registrada", mas a lista continua vazia depois de recarregar
O que esperava: a medição na lista
```

Anexe a hora (com fuso) e, se der, o `request_id` que aparece na mensagem de erro — com ele quem for
corrigir acha a requisição no log sem adivinhar.

**Não anexe senha, token, cookie nem captura de tela que mostre qualquer um dos três.**

## 6. O que já se sabe — não relate

| Comportamento | Não é defeito porque |
|---|---|
| Cadastro responde 503 `legal_documents_not_published` | As 11 minutas jurídicas não passaram por advogado; o banco recusa aceite de rascunho |
| Nenhuma cobrança funciona | Nenhum provedor de pagamento ligado |
| Nota fiscal, retenção e incentivo fiscal não saem | Nenhum provedor fiscal ligado |
| gov.br, ICP-Brasil, assinatura qualificada, biometria, KYC | Exigem credencial e certificado de terceiro |
| SMS e WhatsApp não chegam | Nenhuma conta de envio ligada |
| As 14 integrações aparecem como bloqueadas | Todas em `BLOCKED` por falta de credencial do fornecedor |
| Botão de SSO não aparece na tela de entrar | Defeito **conhecido**: `/entrar` chama `GET /v1/meta/config`, que o backend não registra. A chamada falha calada |
| 231 operações de API não têm tela | Backend à frente da interface; está medido e documentado |
| Leitor de tela e navegação por voz com falhas | Pendências declaradas em `ACCESSIBILITY_REPORT.md`; não se fecham por software |

## 7. O que esta rodada de testes **não** prova

Dizer isso agora evita conclusão errada depois:

- Teste manual não prova isolamento entre organizações. Quem prova é a RLS no banco, e ela tem teste
  próprio na suíte.
- Teste em staging com poucos registros não prova desempenho. O teste de carga é outro instrumento.
- Nenhuma quantidade de teste autoriza a frase "impossível de invadir". Nenhum sistema ligado à
  internet recebe essa garantia, e esta plataforma não vai reivindicá-la.
