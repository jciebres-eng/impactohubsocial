# Matriz de cobertura — v0.28.0

> Gerada por `scripts/make_coverage_matrix.py` a partir das evidências dos testes. Não edite à mão.

Três provas independentes, todas executadas (não planejadas):

- **Jornadas pela API** — 274 passos em 16 jornadas, 0 falha(s). Fonte: `docs/evidence/jornadas_v0250/relatorio.json`.
- **Telas no navegador (Chromium)** — 857 visitas às 235 rotas do roteador. Fonte: `docs/execution/ROUTE_RUNTIME_MATRIX.csv`.
- **Telefone (390 px)** — 245 telas de menu, 0 falha(s). Fonte: `docs/evidence/responsivo_v0250/resumo.json`.

## Por perfil

| Perfil | Jornadas | Passos de API | Falhas de API | Telas visitadas | Com dado | Vazias | Recusa correta | Sem registro próprio | Outras | Telefone: telas | Telefone: vazam |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| OSC | 15 | 160 | 0 | 160 | 139 | 11 | 7 | 3 | 0 | 51 | 0 |
| Empresa (financiador) | 8 | 50 | 0 | 107 | 83 | 18 | 0 | 6 | 0 | 39 | 0 |
| Profissional | 4 | 12 | 0 | 100 | 63 | 25 | 1 | 11 | 0 | 33 | 0 |
| Governo | 1 | 9 | 0 | 195 | 64 | 27 | 84 | 20 | 0 | 36 | 0 |
| Apoiadora (pessoa física) | 3 | 11 | 0 | 101 | 67 | 21 | 1 | 12 | 0 | 27 | 0 |
| Administração | 6 | 25 | 0 | 154 | 112 | 29 | 0 | 13 | 0 | 59 | 0 |
| Editora (equipe) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | — |
| Revisor (equipe) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | — |
| Suporte (equipe) | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | — |
| Visitante sem login | 2 | 4 | 0 | 40 | 29 | 3 | 8 | 0 | 0 | — | — |

**Como ler.** *Com dado*: a tela abriu com conteúdo vindo da API. *Vazias*: abriu e mostrou o estado
vazio do produto (lista sem item, busca sem termo). *Recusa correta*: perfil que NÃO deve ver a tela
recebeu "área não disponível" (ou foi mandado entrar). *Sem registro próprio*: a tela depende de um
registro e esse perfil não participa de nenhum daquele tipo na demonstração — a tela é provada por
outro perfil que participa. *Outras*: qualquer outro estado é falha e derruba o teste.

## Jornadas

| Jornada | Passos | Falhas |
| --- | ---: | ---: |
| Preparação: contas de demonstração e plano concedido pela administração | 9 | 0 |
| OSC: projeto → diagnóstico → impacto | 28 | 0 |
| Financiador: edital → candidatura → aporte → validação | 29 | 0 |
| Rede: proposta → conversa → prestação de contas | 12 | 0 |
| Profissional: necessidade → oferta → revisão técnica | 9 | 0 |
| Governo: edital público → necessidade do território | 25 | 0 |
| Captação: cotas → apoios → campanha pública | 24 | 0 |
| Documentos: montagem → acordo assinado → registro verificável | 20 | 0 |
| Contrato como regra: financiamento → vigência → entrega → aceite → obrigações → nova versão | 37 | 0 |
| Marketplace, soluções e perfis públicos | 6 | 0 |
| Caminho dourado: acordo → aporte direcionado → confirmação → entrega aceita → quitação → reconhecimento → torre | 29 | 0 |
| Central de IA: cota → prévia → originalidade → patrocínio → pedido piloto → painel | 18 | 0 |
| Suporte e Central de Conhecimento | 4 | 0 |
| Banco de Ideias: ideia → amadurecimento → projeto | 5 | 0 |
| Administração: visão geral → verificação → auditoria | 7 | 0 |
| Pendências: o que espera decisão de alguém | 12 | 0 |

## Por rota (resumo)

Uma linha por rota; a coluna de perfis mostra o estado de cada visita (o detalhe completo, com
URL, chamadas de API e tempo, está no CSV).

| Rota | Visitas | Estados por perfil |
| --- | ---: | --- |
| `/` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/@:handle` | 2 | anônimo: ok, osc: ok |
| `/acordos` | 6 | osc: ok, company: ok, provider: ok, government: vazia, individual: ok, admin: vazia |
| `/acordos/:id` | 6 | osc: ok, company: ok, provider: ok, government: s/registro, individual: ok, admin: s/registro |
| `/acordos/novo` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/admin` | 2 | admin: ok, government: recusa |
| `/admin/auditoria` | 2 | admin: ok, government: recusa |
| `/admin/central` | 2 | admin: ok, government: recusa |
| `/admin/central/analytics` | 2 | admin: ok, government: recusa |
| `/admin/central/artigos` | 2 | admin: ok, government: recusa |
| `/admin/central/artigos/:slug` | 2 | admin: ok, government: recusa |
| `/admin/central/cursos` | 2 | admin: ok, government: recusa |
| `/admin/central/equipe` | 2 | admin: ok, government: recusa |
| `/admin/central/eventos` | 2 | admin: ok, government: recusa |
| `/admin/central/faqs` | 2 | admin: ok, government: recusa |
| `/admin/central/parcerias` | 2 | admin: ok, government: recusa |
| `/admin/central/recursos` | 2 | admin: ok, government: recusa |
| `/admin/central/suporte` | 2 | admin: ok, government: recusa |
| `/admin/central/suporte/:id` | 2 | admin: ok, government: recusa |
| `/admin/chaves` | 2 | admin: ok, government: recusa |
| `/admin/cobranca` | 2 | admin: ok, government: recusa |
| `/admin/compliance` | 2 | admin: ok, government: recusa |
| `/admin/conciliacao` | 2 | admin: vazia, government: recusa |
| `/admin/contribuicao` | 2 | admin: ok, government: recusa |
| `/admin/convenios` | 2 | admin: ok, government: recusa |
| `/admin/credenciais` | 2 | admin: vazia, government: recusa |
| `/admin/credenciais-profissionais` | 2 | admin: vazia, government: recusa |
| `/admin/denuncias` | 2 | admin: ok, government: recusa |
| `/admin/doacoes` | 2 | admin: vazia, government: recusa |
| `/admin/doacoes/risco` | 2 | admin: vazia, government: recusa |
| `/admin/editais` | 2 | admin: ok, government: recusa |
| `/admin/erros` | 2 | admin: ok, government: recusa |
| `/admin/fiscal` | 2 | admin: ok, government: recusa |
| `/admin/honorarios` | 2 | admin: ok, government: recusa |
| `/admin/ia/financeiro` | 2 | admin: ok, government: recusa |
| `/admin/identidade` | 2 | admin: ok, government: recusa |
| `/admin/institucional` | 2 | admin: ok, government: recusa |
| `/admin/integracoes` | 2 | admin: ok, government: recusa |
| `/admin/integridade` | 2 | admin: ok, government: recusa |
| `/admin/interruptor` | 2 | admin: ok, government: recusa |
| `/admin/linha-do-tempo` | 2 | admin: ok, government: recusa |
| `/admin/medidas` | 2 | admin: ok, government: recusa |
| `/admin/organizacoes` | 2 | admin: ok, government: recusa |
| `/admin/permissoes` | 2 | admin: ok, government: recusa |
| `/admin/proveniencia` | 2 | admin: ok, government: recusa |
| `/admin/rastro` | 2 | admin: ok, government: recusa |
| `/admin/remuneracao` | 2 | admin: ok, government: recusa |
| `/admin/risco` | 2 | admin: ok, government: recusa |
| `/admin/solucoes` | 2 | admin: ok, government: recusa |
| `/admin/usuarios` | 2 | admin: ok, government: recusa |
| `/admin/vouchers` | 2 | admin: ok, government: recusa |
| `/administrativo/orcamento` | 2 | admin: ok, government: recusa |
| `/afirmacoes` | 6 | osc: ok, company: vazia, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/ajuda` | 2 | anônimo: ok, osc: ok |
| `/ajuda/:slug` | 2 | anônimo: ok, osc: ok |
| `/ajuda/academia` | 2 | anônimo: ok, osc: ok |
| `/ajuda/academia/:slug` | 2 | anônimo: ok, osc: ok |
| `/ajuda/academia/aula/:id` | 2 | anônimo: recusa, osc: ok |
| `/ajuda/atividades` | 2 | anônimo: recusa, osc: ok |
| `/ajuda/biblioteca` | 2 | anônimo: ok, osc: ok |
| `/ajuda/biblioteca/:slug` | 2 | anônimo: ok, osc: ok |
| `/ajuda/boletim` | 2 | anônimo: ok, osc: ok |
| `/ajuda/boletim/cancelar` | 2 | anônimo: vazia, osc: vazia |
| `/ajuda/boletim/confirmar` | 2 | anônimo: vazia, osc: vazia |
| `/ajuda/busca` | 2 | anônimo: vazia, osc: vazia |
| `/ajuda/certificado/:code` | 2 | anônimo: ok, osc: ok |
| `/ajuda/comece-aqui` | 2 | anônimo: recusa, osc: ok |
| `/ajuda/demonstracao` | 2 | anônimo: ok, osc: ok |
| `/ajuda/eventos` | 2 | anônimo: ok, osc: ok |
| `/ajuda/eventos/:slug` | 2 | anônimo: ok, osc: ok |
| `/ajuda/faq` | 2 | anônimo: ok, osc: ok |
| `/ajuda/faq/:id` | 2 | anônimo: ok, osc: ok |
| `/ajuda/glossario` | 2 | anônimo: ok, osc: ok |
| `/ajuda/parcerias` | 2 | anônimo: ok, osc: ok |
| `/ajuda/pendencias` | 2 | anônimo: recusa, osc: ok |
| `/ajuda/preferencias` | 2 | anônimo: recusa, osc: ok |
| `/ajuda/suporte` | 2 | anônimo: recusa, osc: ok |
| `/ajuda/suporte/:id` | 2 | anônimo: recusa, osc: ok |
| `/ajuda/suporte/novo` | 2 | anônimo: recusa, osc: ok |
| `/aprovacoes` | 2 | admin: ok, government: recusa |
| `/area` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/assinatura/politica` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/assinatura/provedores` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/auditoria` | 2 | admin: ok, government: recusa |
| `/cadastro` | 1 | anônimo: ok |
| `/campanha-gestao` | 2 | osc: ok, government: recusa |
| `/campanha/:slug` | 2 | anônimo: ok, osc: ok |
| `/candidaturas` | 6 | osc: ok, company: ok, provider: vazia, government: ok, individual: ok, admin: vazia |
| `/candidaturas/:id` | 6 | osc: ok, company: ok, provider: s/registro, government: ok, individual: ok, admin: s/registro |
| `/carteira` | 4 | company: ok, government: vazia, individual: vazia, osc: recusa |
| `/compras/:id` | 2 | osc: ok, government: s/registro |
| `/conquistas` | 4 | osc: ok, provider: ok, company: ok, government: recusa |
| `/conta` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/conta/acesso` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/conta/comercial` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/conta/consumo` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/conta/denuncias` | 6 | osc: vazia, company: vazia, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/conta/moderacao` | 6 | osc: vazia, company: vazia, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/conta/plano` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/conta/preferencias` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/conta/seguranca` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/contabilidade` | 2 | admin: ok, government: recusa |
| `/contabilidade/plano-de-contas` | 2 | admin: ok, government: recusa |
| `/contribuicoes` | 3 | company: ok, government: vazia, osc: recusa |
| `/controladoria` | 2 | admin: ok, government: recusa |
| `/controladoria/conciliacao` | 2 | admin: ok, government: recusa |
| `/controladoria/torre` | 2 | admin: ok, government: recusa |
| `/conversas` | 6 | osc: ok, company: ok, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/conversas/:id` | 6 | osc: ok, company: ok, provider: s/registro, government: s/registro, individual: s/registro, admin: s/registro |
| `/convite` | 1 | anônimo: ok |
| `/cotas` | 2 | osc: ok, government: recusa |
| `/cotas/:id/apoios` | 2 | osc: ok, government: s/registro |
| `/dados-territoriais` | 3 | government: ok, admin: ok, osc: recusa |
| `/determinantes` | 3 | government: ok, admin: ok, osc: recusa |
| `/diagnosticos` | 2 | osc: ok, government: recusa |
| `/diagnosticos/:id` | 2 | osc: ok, government: s/registro |
| `/diagnosticos/:id/roteiro` | 2 | osc: ok, government: s/registro |
| `/diagnosticos/:id/versoes` | 2 | osc: ok, government: s/registro |
| `/doacao/:id` | 2 | anônimo: ok, osc: ok |
| `/documentos` | 6 | osc: ok, company: vazia, provider: vazia, government: vazia, individual: vazia, admin: ok |
| `/documentos/modelos` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/documentos/montagens` | 6 | osc: ok, company: vazia, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/documentos/montagens/:id` | 6 | osc: ok, company: s/registro, provider: s/registro, government: s/registro, individual: s/registro, admin: s/registro |
| `/editais` | 3 | company: ok, government: ok, osc: recusa |
| `/editais/:id/candidaturas` | 3 | company: ok, government: vazia, osc: s/registro |
| `/editais/:id/editar` | 3 | company: ok, government: ok, osc: s/registro |
| `/editais/novo` | 3 | company: ok, government: ok, osc: recusa |
| `/entrar` | 1 | anônimo: ok |
| `/esqueci-senha` | 1 | anônimo: ok |
| `/explorar` | 3 | company: ok, individual: ok, government: recusa |
| `/extratos` | 2 | osc: ok, government: recusa |
| `/financeiro` | 2 | admin: ok, government: recusa |
| `/financeiro/despesas` | 2 | admin: ok, government: recusa |
| `/financeiro/instrucoes` | 2 | admin: ok, government: recusa |
| `/financeiro/periodos-gratuitos` | 2 | admin: ok, government: recusa |
| `/fiscal` | 2 | company: ok, government: recusa |
| `/ia` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/ia/analises/:id` | 6 | osc: ok, company: s/registro, provider: s/registro, government: s/registro, individual: s/registro, admin: s/registro |
| `/ia/orcamento` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/ia/patrocinios/:id` | 6 | osc: s/registro, company: ok, provider: s/registro, government: s/registro, individual: s/registro, admin: s/registro |
| `/ideias` | 2 | osc: ok, government: recusa |
| `/identidade` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/instituicao` | 5 | osc: ok, company: ok, government: ok, provider: ok, individual: ok |
| `/instituicoes/:id` | 6 | osc: vazia, company: ok, provider: vazia, government: ok, individual: ok, admin: ok |
| `/legal/privacidade` | 1 | anônimo: ok |
| `/legal/termos` | 1 | anônimo: ok |
| `/mapa` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/marketplace` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/marketplace/:id` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/marketplace/meus` | 6 | osc: ok, company: vazia, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/marketplace/novo` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/materiais` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/mensagens` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/mensagens/:id` | 6 | osc: ok, company: ok, provider: s/registro, government: s/registro, individual: s/registro, admin: s/registro |
| `/minhas-atividades` | 3 | provider: vazia, individual: vazia, government: recusa |
| `/minhas-doacoes` | 6 | osc: vazia, company: ok, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/necessidades/:id` | 2 | osc: ok, government: s/registro |
| `/notificacoes` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: vazia |
| `/operacoes` | 2 | admin: ok, government: recusa |
| `/operacoes/alertas` | 2 | admin: ok, government: recusa |
| `/oportunidades` | 2 | osc: ok, government: recusa |
| `/oportunidades-profissionais` | 2 | provider: ok, government: recusa |
| `/oportunidades/:id` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/organizacao` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/organizacao/compliance` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/organizacao/equipe` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/organizacao/nova` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/pagamentos` | 5 | osc: ok, company: ok, individual: vazia, government: vazia, provider: recusa |
| `/pagamentos/:id` | 5 | osc: ok, company: ok, individual: s/registro, government: s/registro, provider: s/registro |
| `/participacoes` | 5 | osc: ok, individual: ok, provider: vazia, company: vazia, government: recusa |
| `/perfil-publico` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/perfil-publico/:id/identificadores` | 6 | osc: vazia, company: s/registro, provider: vazia, government: s/registro, individual: s/registro, admin: s/registro |
| `/perfil-publico/experiencias` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/planos` | 1 | anônimo: ok |
| `/portal` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/profissionais` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/projetos` | 2 | osc: ok, government: recusa |
| `/projetos/:id` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/projetos/:id/apoio-profissional` | 2 | osc: ok, government: recusa |
| `/projetos/:id/compras` | 2 | osc: ok, government: recusa |
| `/projetos/:id/contribuicao` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/projetos/:id/dossie` | 6 | osc: ok, company: ok, provider: s/registro, government: s/registro, individual: s/registro, admin: s/registro |
| `/projetos/:id/equidade` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/projetos/:id/equipe` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/projetos/:id/grafo` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/projetos/:id/impacto` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/projetos/:id/linha-do-tempo` | 2 | osc: ok, government: recusa |
| `/projetos/:id/localizacao` | 2 | osc: ok, government: recusa |
| `/projetos/:id/ods` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/projetos/:id/relatorios` | 6 | osc: ok, company: vazia, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/projetos/:id/retratos` | 2 | osc: ok, government: recusa |
| `/projetos/:id/riscos` | 2 | osc: ok, government: recusa |
| `/projetos/:id/situacao` | 2 | osc: ok, government: recusa |
| `/projetos/novo` | 2 | osc: ok, government: recusa |
| `/prontidao` | 2 | osc: ok, government: recusa |
| `/prontidao/finalidades` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/propostas` | 6 | osc: ok, company: vazia, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/propostas/:id` | 6 | osc: ok, company: ok, provider: ok, government: s/registro, individual: s/registro, admin: s/registro |
| `/propostas/nova` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/rascunhos` | 6 | osc: ok, company: vazia, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/rascunhos/:id` | 6 | osc: ok, company: s/registro, provider: s/registro, government: s/registro, individual: s/registro, admin: s/registro |
| `/rede/atividade` | 6 | osc: ok, company: ok, provider: ok, government: vazia, individual: ok, admin: vazia |
| `/rede/experiencias` | 6 | osc: ok, company: vazia, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/rede/grafo` | 6 | osc: vazia, company: vazia, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/rede/relacoes` | 6 | osc: ok, company: ok, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/redefinir-senha` | 1 | anônimo: ok |
| `/relatorios` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/relatorios-impacto` | 6 | osc: vazia, company: ok, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/relatorios-impacto/:id` | 6 | osc: ok, company: ok, provider: s/registro, government: s/registro, individual: s/registro, admin: s/registro |
| `/remuneracao` | 5 | osc: ok, company: ok, provider: ok, government: ok, individual: recusa |
| `/reputacao` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/responsabilidade` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/revisoes` | 6 | osc: ok, company: vazia, provider: ok, government: vazia, individual: vazia, admin: vazia |
| `/revisoes/:id` | 6 | osc: ok, company: s/registro, provider: ok, government: s/registro, individual: s/registro, admin: s/registro |
| `/selos` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/settings/billing` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/solucoes` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/solucoes/:id` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/solucoes/:id/editar` | 5 | osc: ok, individual: ok, company: s/registro, government: s/registro, provider: s/registro |
| `/solucoes/comparar` | 6 | osc: vazia, company: vazia, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/solucoes/minhas` | 6 | osc: ok, company: vazia, provider: vazia, government: vazia, individual: ok, admin: vazia |
| `/solucoes/nova` | 5 | osc: ok, individual: ok, company: ok, government: ok, provider: ok |
| `/solucoes/pedidos` | 6 | osc: ok, company: vazia, provider: vazia, government: vazia, individual: ok, admin: vazia |
| `/solucoes/preferencias` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/solucoes/replicacao` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/solucoes/replicacoes` | 6 | osc: ok, company: vazia, provider: vazia, government: vazia, individual: ok, admin: vazia |
| `/territorio/necessidades` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
| `/tesouraria` | 2 | admin: ok, government: recusa |
| `/torre` | 3 | company: ok, individual: ok, government: recusa |
| `/torre-territorial` | 3 | government: ok, admin: ok, osc: recusa |
| `/verificacoes` | 6 | osc: ok, company: vazia, provider: vazia, government: vazia, individual: vazia, admin: vazia |
| `/verificar` | 2 | anônimo: ok, osc: ok |
| `/verificar-email` | 1 | anônimo: ok |
| `/verificar/:code` | 2 | anônimo: ok, osc: ok |
| `/vocabulario` | 6 | osc: ok, company: ok, provider: ok, government: ok, individual: ok, admin: ok |
