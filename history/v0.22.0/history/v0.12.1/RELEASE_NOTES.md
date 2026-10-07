# Release notes — v0.11.0

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
