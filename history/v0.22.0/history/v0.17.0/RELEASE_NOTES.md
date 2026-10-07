# Release notes — v0.17.0

## v0.17.0 — Camada econômica, legal e de pagamento

**Resumo:** a plataforma passou a saber **quem paga, por quê, e o que ela ainda não pode cobrar**. A rodada inverte a
ordem do roteiro a pedido do proprietário — monetização, pagamento e auditoria legal **antes** do design — e
implementa uma tese só: **o proponente não pode ser o pagador principal.**

### Para quem usa

- **Entrada gratuita, de forma permanente.** Cadastro, perfil, criação de projeto, descoberta de oportunidades,
  participação na rede e acompanhamento básico são gratuitos e seguem gratuitos. O plano chama-se "OSC — gratuito"
  porque é isso que ele é. Atingir um limite técnico não tira o acesso ao que já foi criado.
- **Programa**, para quem financia: a carteira, as chamadas, os indicadores e as necessidades de território num
  lugar só — com **gasto** e **comprovado** em colunas separadas, a força declarada de cada elo da cadeia de
  resultado, e a lacuna territorial com a qualidade da evidência que a sustenta.
- **Onze documentos legais** publicados como minuta, cada um dizendo em letras o que a plataforma **não** faz.
- **O que a plataforma entregou** passou a ser um registro próprio, separado do que ela cobrou.

### O que você vai ver escrito, e é verdade

- **`PRODUCTION PAYMENT NOT CONFIGURED`** em toda a área de pagamento. Não há provedor contratado, então **nenhuma
  cobrança real foi processada** — e cada cobrança de teste aparece marcada como simulada, em cada linha, não só no
  resumo.
- **Nenhuma receita ativa.** Nove regras cadastradas, nenhuma liberada: cinco esperam parecer jurídico e quatro
  foram recusadas.
- **Nenhum aceite de termos é registrável.** As minutas não passaram por advogado(a), e o banco recusa registrar
  aceite de rascunho — porque "o usuário aceitou os termos" dito sobre um rascunho é afirmação falsa com aparência
  de prova.
- **Nenhuma estimativa de "horas economizadas".** Sem linha de base declarada com fonte, data e método, o produto
  mostra as contagens que mediu e deixa a estimativa em branco.

### Para quem decide

O que falta para faturar **não é software**: parecer jurídico, provedor de pagamento contratado e contador para
nota fiscal. A lista completa, com o que cada item destrava, está em `MONETIZATION_LEGAL_MATRIX.md` §5 e em
`RELEASE_READINESS.md` §5.

**961 testes, 749 operações, 253 tabelas, 24 migrações.** Um limite declarado: o feed do financiador ficou mais
lento (1,87–2,04 s, folga de 1,2× até o orçamento) e a correção já está nomeada.

## v0.16.0 — IMPACT NETWORK CORE

**Resumo:** a plataforma deixou de ser um lugar com projetos e passou a ser **infraestrutura de impacto** — onde
quem precisa, quem financia, quem executa e quem fiscaliza participam do **mesmo ciclo**, cada um com o seu ambiente
de trabalho, sem quatro aplicações separadas.

**Para a organização que executa:** uma Área de trabalho que diz **o que fazer agora** — não um painel de números.
Anuncia o projeto no marketplace, recebe propostas, aceita e a relação nasce formalizada. No fim do período, presta
contas no mesmo lugar: escreve o relatório, e os **números vêm do que foi lançado** (indicadores, marcos,
evidências) — não há campo para digitar "atendemos 400 pessoas".

**Para quem financia:** descobre projetos, lê a **prontidão** em seis dimensões *com a explicação do que falta*,
acompanha em lista privada, conversa **sempre com contexto**, propõe, e depois recebe a prestação de contas e aceita
ou pede ajuste. E a plataforma nunca diz "investido" quando só houve intenção — intenção, compromisso e transação
são três coisas distintas, com nomes distintos.

**Para o profissional:** página pública própria em **`impacto.app/@seunome`**, com registro profissional conferido e
experiência que só aparece **depois** de a organização citada confirmar. Recebe propostas de serviço e mentoria.

**Para o governo:** registra necessidades do território, publica edital, propõe convênio, acompanha execução e
analisa relatório. O indicador do território se move com o resultado.

**Para toda a equipe:** cada evolução, mudança de etapa ou documento anexado **avisa quem está envolvido** — não só
quem é dono. Catorze grupos de aviso, com preferência por grupo e por canal, e um aviso por fato (nunca dois).

**Também entrou:**

- **Rede visível e controlada:** 22 tipos de relação, cada uma com cinco níveis possíveis de visibilidade — e
  bloquear, favoritar e acompanhar são **sempre privados**. A existência de uma relação nunca implica que ela seja
  pública.
- **Marketplace** onde só o que está publicado aparece, com um único lugar no código que decide isso.
- **Escada de moderação** de dez degraus com regra, motivo, prazo e **direito de contestar** — julgado por quem não
  aplicou. Nada automático, e banimento nunca como primeira resposta.
- **Preço com regra escrita:** 14 dias de teste com o produto completo, **US$ 1,99/mês nos 3 primeiros meses
  pagos**, depois US$ 19,99/mês ou US$ 179,88/ano (equivalente a US$ 14,99/mês), com o total sempre visível e
  imposto declarado no checkout. Aumento de preço exige **30 dias de aviso**; o preço nunca muda em silêncio.
- **Vocabulário comum** (taxonomias versionadas no banco, não listas soltas em cada tela).

**O que esta versão NÃO entrega:** cobrança real (não há conta, chave nem preço no provedor — a plataforma **recusa
cobrar** em vez de inventar), camada de design, aplicativo em loja, notificação no aparelho e validação de segurança
por terceiro. O pacote de Design System "Convergência" **não foi recebido**, e as seções que dependiam dele não
foram executadas. Tudo nomeado em `RELEASE_READINESS.md` §5.

**Números:** 788 testes (0 falhas) · 704 operações de API · 231 tabelas · 17 migrações · 27 telas novas.

**Leia:** `IMPACT_NETWORK_ARCHITECTURE.md`, `DESIGN_HANDOFF_FINAL.md`, `FINAL_IMPACT_NETWORK_HARDENING_REPORT.md`.

---

## v0.15.0 — Núcleo do produto

**Resumo:** as seis peças (ideia, diagnóstico, projeto, documento, match, acompanhamento) passaram a ser **um
sistema**, compartilhando o mesmo vocabulário de evidência — com fonte, data e frescura —, as mesmas versões de
motor e a mesma trilha encadeada por hash. A ideia não é apagada ao virar projeto; a máquina de 17 situações é dado
no banco; o diagnóstico separa FATO, INFERÊNCIA, RECOMENDAÇÃO e **DESCONHECIDO**; a montagem de documento recusa
gerar incompleto dizendo o que falta e exige quatro olhos para aprovar. 673 testes, 625 operações, 205 tabelas.
Documentos: `CORE_PRODUCT_ARCHITECTURE.md`, `FINAL_PRE_DESIGN_HARDENING_REPORT.md`.

---

## v0.14.0 — Confiança, identidade e assinatura digital
**Resumo:** documento assinado na plataforma passou a ser **conferível por qualquer pessoa autorizada**, sem conta: pelo
código impresso ou pelo QR Code, em `/verificar`. A página responde se o documento é genuíno, **qual versão foi
assinada**, se a integridade permanece intacta, quem assinou e se foi revogado.
- **Para quem recebe o documento:** confere em segundos, sem login, e vê se existe versão mais nova.
- **Para quem assina:** assinatura em duas camadas (senha + código de uso único por e-mail) amarrada à versão exata do
  conteúdo — se o documento muda, o código deixa de valer.
- **Para a organização:** cadeia de custódia de cada documento, revogação com motivo visível, acordos assinados por todas
  as partes com acompanhamento das entregas, identidade e credencial profissional conferidas por pessoas da equipe.
- **Também entrou:** taxonomia ODS/ESG/determinantes sociais, idioma e tema por usuária, financiamento em cotas com
  campanha pública ("faltam N cotas"), tabela de honorários que só publica com fonte e data, georreferência com
  consentimento, diagnóstico guiado em 8 etapas e exportação em docx, xlsx, odt, ods, xml e PDF com QR.
- **O que NÃO é:** **não há assinatura qualificada (ICP-Brasil ou gov.br)**, nem biometria, nem prova de vida, nem SMS,
  nem carimbo de Autoridade de Carimbo de Tempo. Tudo isso depende de contratação externa e a plataforma **recusa com
  mensagem explicando**, em vez de fingir. "Credencial verificada" significa **documento conferido pela equipe** — a
  plataforma não consulta conselho profissional on-line. Os emblemas oficiais da ONU **não acompanham** a plataforma.
- **Atenção a integrações:** `POST /v1/signatures` passou a exigir o campo `code`. Quem assinava com senha apenas precisa
  pedir o código antes (`POST /v1/signatures/challenge`).
- Leia `PUBLIC_VERIFICATION.md` e `FINAL_TRUST_HARDENING_REPORT.md`.

## v0.13.0 — Integration Hub (fundação)
**Resumo:** a plataforma passou a conversar com sistemas externos por uma camada própria, desacoplada: conexões por ambiente, credenciais cifradas que a API nunca devolve, mapeamento de campos, correspondência de ID externo com conflito explícito, jobs idempotentes com repetição e disjuntor, webhooks de entrada e saída assinados, importação CSV/XLSX com aprovação humana, exportação e um painel que responde “qual integração está quebrada agora”.
- **Para quem contrata:** dá para conectar um ERP (Senior, TOTVS) ou qualquer API REST sem mexer no núcleo do produto, e trocar de fornecedor sem reescrever o sistema.
- **Para a equipe:** 36 rotas novas, 13 tabelas, 9 provedores no catálogo com **maturidade honesta**, 76 testes novos (468 no total).
- **O que NÃO é:** **nenhuma integração foi executada contra um sistema externo real** — tudo foi provado contra dublê. Nenhum provedor está homologado. Integração com governo exige credenciamento e o adapter **recusa agir** enquanto isso. SFTP não foi implementado. E **não existe nenhuma tela** — a interface é a próxima etapa.
- Leia `INTEGRATION_HUB.md` e `FINAL_INTEGRATION_HARDENING_REPORT.md`.

## v0.12.0 — Central de Conhecimento
**Resumo:** hub de ajuda (guias, busca, ajuda contextual, biblioteca, FAQ, assistente ancorado), Academia com quiz e certificado não oficial, eventos, suporte com SLA, parcerias, demonstração, solicitação de teste, boletim e CMS editorial com quatro olhos. **Não há conteúdo oficial real publicado** — só exemplos rotulados.
- **Quem usa:** qualquer pessoa pode buscar, ler guias públicos, ver eventos/cursos, pedir demonstração, propor parceria e assinar o boletim (com confirmação por e-mail). Quem entrou salva checklists, faz cursos, abre chamados e se inscreve em eventos.
- **Equipe:** `/admin/central` (editor escreve; revisor aprova e publica — outra pessoa). Suporte atende pela fila com SLA.
- **Avisos por e-mail** agora saem para cobrança, suporte e eventos (respeitando `/ajuda/preferencias`).
- **O que NÃO é:** o assistente não usa IA generativa; certificados não são oficiais; SLA inicial é hipótese; preços e Stripe real continuam pendentes. Veja `KNOWLEDGE_HUB.md` §4.1.
- Atualização: aplicar a migração `0009`; configurar o worker para o job `hub_ops`; opcionalmente `kb-import` para criar rascunhos.

---


**Resumo v0.11.0:** monetização completa sobre o billing existente — níveis FREE/PLUS/PREMIUM/GOV, trial de 14 dias FULL sem cartão, cobrança mensal/anual por Stripe (webhooks seguros), vouchers, licenças e convênios, tudo com preço/desconto/direitos decididos no servidor. **Preços ainda não definidos e Stripe ainda não homologado** (`docs/billing.md`).
## Para qualquer organização
- Ao se cadastrar você recebe **14 dias de acesso FULL, sem cartão**. Você pode cancelar a qualquer momento: o acesso FULL continua até o fim do teste, **nenhuma cobrança é feita**, e depois a conta passa ao plano gratuito — seus dados e histórico financeiro permanecem.
- Página **Plano e cobrança** (`/conta/plano`): mensal/anual com a economia real, valor final calculado pelo servidor, voucher, código de convênio, cancelar/manter assinatura, faturas e portal de pagamento.
- Falha de pagamento: aviso claro, sem corte imediato e sem perda de dados.
## Para a administração
- Vouchers de desconto (%/valor/100%/permanente), convênios (código + vagas + plano/desconto, ativação por 2º admin), licenças com origem e revogação, trial concedido com motivo, preço do plano — tudo auditado.
## Limites desta versão
Sem preços definidos, a contratação online é recusada. Stripe só foi simulado em testes. Avisos apenas dentro da plataforma.


**Resumo:** fecha as pendências da camada institucional do v0.10.0 que podiam ser resolvidas sem infraestrutura externa. Nada aqui é parecer jurídico nem certificação governamental.

## Para OSCs, OS, OSCIP e coletivos
- Abas novas em **Instituição**: *OS / OSCIP* (qualificações, autoridade, áreas, alertas de validade, próximos passos), *Instrumentos* (contratos de gestão e termos — **declarados** até a administração verificar) e *Formalização e mentoria* (trilha de 11 etapas e pedido de mentoria humana).
- Qualificações aceitam **áreas de atuação**.
## Para financiadores
- Estimativa fiscal de um projeto mostra, **em separado**, se a OSC proponente está elegível institucionalmente.
- Nas soluções, **“Ver rede de relações”**: autoria, território, ODS, temas, soluções relacionadas e demanda agregada (sem identificar organizações).
## Para a administração
- Filas de **instrumentos** e de **mentoria** no painel institucional (testadas no navegador com MFA real).
## Limites honestos
- Trilha, catálogos e regras seguem como hipótese sem revisão jurídica; IA sobre documentos **não existe**; Android/iOS não construídos; sem linter além de `tsc`/`compileall`.

---
# Release notes — v0.10.0 (anterior)

**Resumo:** adiciona a **camada institucional do terceiro setor**: a plataforma passa a distinguir o que a organização *é* (natureza jurídica), o que *declara* e o que *comprovou* (qualificações e documentos), em que **situação** está e se **pode concorrer a uma oportunidade específica** — sempre com explicação, fonte e o que falta, e sem prometer recurso nem benefício fiscal.

## Para OSCs e coletivos
- Página **Instituição**: natureza jurídica, qualificações (declaradas × verificadas), documentos (AUSENTE · PENDENTE DE VALIDAÇÃO · VALIDADO · EXPIRADO · REJEITADO), maturidade 0–6 e "o que falta".
- Coletivos sem CNPJ podem se cadastrar e participar do que não exige CNPJ.
- Verificar elegibilidade para um edital: 5 estados, com requisito a requisito.
## Para financiadores, empresas e governo
- Critérios institucionais em editais e perfil do financiador; match mostra **bloqueios explicados**.
- Biblioteca de soluções com filtros por natureza jurídica, qualificação verificada, modalidade e prontidão para financiamento.
## Para a administração
- Fila de qualificações e documentos; regras e catálogos com rascunho → revisão → aprovação (por outra pessoa) → publicação.
## O que mudou de comportamento
- Certificação exigida por edital só é aceita se **verificada** pela administração.
## Limites honestos
- Catálogos e regras iniciais são classificação da plataforma, **sem revisão jurídica**; sem integração com bases governamentais; badges não são certificação governamental.

---
# Release notes — v0.9.0 (anterior)

**Resumo:** além do fluxo OSC → edital/fundo → candidatura → execução → prestação de contas (v0.7.0) e dos módulos de impacto, compras, pagamentos registrados, risco, rede, mapa e relatórios (v0.8.0, incluído), esta versão traz a **Biblioteca de Soluções de Impacto**: um banco inteligente de ideias, projetos, metodologias, tecnologias sociais e projetos acadêmicos.

## Biblioteca de Soluções
- **Buscar por intenção**: "artes caps", "projeto idosos", "tenho R$ 250 mil para saúde mental no MT" — o sistema mostra o que entendeu e **por que** cada resultado apareceu.
- **Entender a confiança**: cada solução mostra quem declarou, o que tem evidência, o que foi validado e o que foi apenas autodeclarado. Ideia nunca vira case; "comprovado" só com revisão da administração.
- **Agir**: comparar 2–4 soluções, combinar, "quero algo como este", adaptar para meu território, desenvolver uma ideia (rascunho que exige revisão humana), pedir informações/contato/replicação, declarar interesse de financiamento (identidade privada por padrão), replicar e ter a replicação confirmada pelo autor.
- **Financiadores**: tese de investimento, match explicável e recomendações (personalização só com consentimento).
- **Administração**: fila de verificação, revisão de evidências, validação de resultados, remoção e contestações de autoria.

## Números reais
API 306 operações · 105 tabelas · 207 políticas RLS · 182 testes · busca p95 ≈ 474 ms com 5.000 soluções sintéticas (local).

## Limites (leia)
Sem embeddings (tesauro + FTS + trigramas) · IA opcional e **não usada** na busca/copiloto · pesos de relevância são hipóteses · todos os dados são DEMO · nada foi publicado (web/lojas) · textos legais são minutas [VALIDAR JURÍDICO] · fiscal sem regras aprovadas · pagamentos são registro, sem custódia.

## Atualização
Instale do zero (`ENVIRONMENT_SETUP.md`); migrações 0001–0005 aplicam em sequência. Não há dados legados a migrar. Histórico de versões em `history/`.
