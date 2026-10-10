# Decisões da camada IES (D-01 a D-17)

Formato: decisão · alternativas consideradas · por que esta · impacto/migração · quem pode mudar. As decisões que dependem do
responsável ou da IES estão marcadas **[RESPONSÁVEL]** ou **[IES]**; as demais são técnicas e foram tomadas com a opção mais segura
que preserva o objetivo (regra 11 do kit). Nada aqui afirma conformidade regulatória.

## D-01 — A IES é uma organização que já existe, com um perfil institucional; não é um novo tipo de organização

- **Decisão:** `academic_institutions` (1 linha por organização) liga a capacidade "ensino superior" a uma organização dos tipos
  `osc`, `company` ou `government`. A organização continua com o seu tipo, a sua natureza jurídica e as suas regras.
- **Alternativas:** (a) novo `kind = 'ies'`; (b) manter a IES como `osc` (o que acontece hoje via natureza jurídica).
- **Por quê:** a natureza jurídica de uma IES varia — universidade federal é autarquia (`government`), faculdade privada com fins
  lucrativos é empresa (`company`), comunitária/confessional/filantrópica é associação ou fundação (`osc`). Um tipo novo mexeria em
  ~100 declarações `kinds=`, nos pacotes base, nas políticas `app_kind()` e nas regras de dinheiro público. (b) erra para a IES
  pública e para a privada com fins lucrativos.
- **Impacto:** a natureza `academic_institution` do catálogo passa a aceitar os três tipos; ativação do perfil por pessoa da equipe
  com a permissão que já existe para aprovar e verificar organizações (`admin.organizations.write`, da conformidade), confirmação
  de identidade (já é permissão com step-up) e trilha. Nenhuma permissão nova. Categoria administrativa (pública federal/estadual/
  municipal; privada com/sem fins lucrativos) é **declarada** pela IES — a plataforma não a certifica.

## D-02 — Estudante e docente são pessoas (`users`), não membros da organização IES

- **Decisão:** administração da IES = dono/administrador da organização (reuso de `memberships`). Estudantes, docentes,
  coordenações e gestão acadêmica são **vínculos acadêmicos com escopo** em tabela própria (`academic_roles`): papel
  (`academic_manager`, `coordinator`, `teacher`, `student`) × escopo (instituição, curso, oferta) × validade × revogação.
- **Alternativas:** tornar estudantes `member`/`viewer` da organização IES.
- **Por quê:** a RLS dá a qualquer membro acesso ao que a organização vê (projetos, documentos, finanças, acordos). Um estudante
  veria o financeiro da instituição. O adendo pede "não criar estrutura de papéis paralela **se o núcleo já oferecer**" — o núcleo
  não oferece papel com escopo menor que a organização (auditoria, §3). Registrado como ampliação, não duplicação: a identidade, a
  sessão, o convite e a auditoria são os mesmos.
- **Impacto:** quem só tem vínculo acadêmico usa o produto **sem organização ativa** (hoje impossível — a tela obriga a criar uma).

## D-03 — Autorização acadêmica no servidor e no banco, a cada requisição

- **Decisão:** rotas `/v1/edu/...` com `auth="user"`; o serviço confere o vínculo no banco a cada chamada; as tabelas acadêmicas
  têm RLS com funções `edu_*()` (SECURITY DEFINER, `search_path` terminado em `pg_temp`, EXECUTE só para `impacto_app`) baseadas em
  `app_uid()`. O identificador da instituição vem na URL e é **sempre** reconferido; nada é confiado ao navegador.
- **Por quê:** testes negativos de IDOR/troca de ID precisam falhar no muro (banco), não só na porta (rota) — padrão da casa
  (`CrossTenantIsRefusedByTheWallNotOnlyByTheDoorTests`).

## D-04 — Licença institucional sem assinatura (ADR-341) e sem preço inventado [RESPONSÁVEL]

- **Decisão:** `academic_licenses`: instituição, assentos de estudante, validade, origem (`contract`, `convention`, `voucher`,
  `courtesy`), referência do contrato. **Quatro olhos** como nos convênios (ADR-063): uma pessoa da equipe com `billing.write`
  (a permissão das concessões, com step-up) propõe; **outra** ativa. Assento é consumido quando o estudante ativa o vínculo. **Nenhum preço** no
  sistema, nenhuma cobrança, nenhuma recorrência. Contrato avulso/parcelado e concessões existentes continuam sendo o caminho
  comercial (ADR-341, ADR-342).
- **Regras desta versão (a validar comercialmente):** sem assento livre, o estudante convidado fica "aguardando assento" (nada
  some); licença vencida não aceita novas ativações, mas quem já está ativo mantém acesso às entregas e à exportação até o fim do
  período letivo vigente, e a leitura/exportação nunca é bloqueada (paralelo da ADR-381).
- **Pendente do responsável:** modelo comercial (pacote por estudante, por turma, convênio), valores e texto do contrato.

## D-05 — IA na camada IES: reaproveita a camada existente; nenhuma operação acadêmica de IA nesta versão

- A camada atual (prévia de custo, cotas, patrocínio, revisão humana) já responde "quem paga". Nenhum provedor externo está ligado;
  as operações assistivas da IES (sugerir mapeamento do plano de ensino) ficam **planejadas** e não são simuladas.

## D-06 — Importação acadêmica cria ROTEIRO e CONVITE, nunca conta de pessoa (preserva ADR-093)

- **Decisão:** importar cursos, componentes, ofertas e matrículas cria registros acadêmicos da IES; uma matrícula importada é uma
  entrada de roteiro (identificador institucional + e-mail institucional + nome de exibição) que vira **convite**; a conta só nasce
  quando a pessoa aceita (cadastro e consentimento próprios).
- Prévia/dry-run com contagens (criar, atualizar, sem mudança, conflito, rejeitar) e erro por linha; nada é gravado na prévia;
  confirmação explícita por pessoa autorizada; idempotência por (instituição, sistema de origem, entidade, ID externo) e pelo
  SHA-256 do arquivo; relatório baixável com neutralização de fórmula por **uma** função comum testada.
- Formatos: CSV UTF-8 (BOM tolerado) e XLSX, pelo leitor seguro que já existe (`integrations/files.py`).

## D-07 — Fonte de verdade declarada por entidade [IES]

- Padrão sugerido (não aplicado sem a IES confirmar): ERP/SIS ou planilha da IES para estrutura acadêmica e matrículas; IMPACTO para
  extensão, evidências, horas e acompanhamento. Divergência vira **conflito registrado**, nunca sobrescrita silenciosa. Trancamento,
  cancelamento, transferência e desligamento mudam **estado**; nada é apagado por importação.

## D-08 — Avaliador externo autorizado: temporário, com escopo, só leitura; nunca "MEC"

- `academic_access_grants`: pessoa convidada por e-mail (precisa de conta — identidade é obrigatória), finalidade escrita, escopo
  (instituição, curso, ação, dossiê), validade máxima de 90 dias, revogação imediata, somente leitura; toda leitura e exportação
  registrada. O rótulo é "avaliador externo autorizado". Nenhuma tela ou texto sugere acesso, credenciamento ou integração oficial do
  MEC, Inep, CAPES ou CNPq.

## D-09 — Horas: quem registra não aprova

- Estados distintos: registrado (rascunho) → submetido → aprovado | devolvido | recusado → exportado. Aprovação só por docente da
  oferta (ou coordenação do curso) **diferente** de quem registrou; motivo obrigatório para devolver/recusar; prevenção de
  duplicidade; limites configuráveis. A plataforma nunca diz que lançou no histórico escolar (só gera arquivo).

## D-10 — Ação de extensão é registro acadêmico próprio, ligado ao que já existe

- Modalidades do art. 8º da Res. CNE/CES 7/2018 (programa, projeto, curso/oficina, evento, prestação de serviço) e comunidade
  externa envolvida obrigatória (art. 7º). Liga-se a ofertas e, quando houver, a `programs`/`projects` existentes e a demandas
  (`territory_needs`, `calls`, organização parceira) — **vínculo, não cópia**.

## D-11 — Ciclo semestral e passagem de bastão só por inclusão

- Ciclo = ação × período letivo. Ao encerrar, a passagem registra linha de base, resultados validados, pendências, riscos,
  consentimentos e limitações; é aprovada pelo docente responsável (e, quando houver, pelo parceiro) e **aceita** pela nova equipe.
  Continuar, pausar ou encerrar é decisão registrada; o histórico nunca é sobrescrito; mudança de método marca quebra de série
  (reuso de `indicator_method_changes`).

## D-12 — Entrega em incrementos, cada um com ZIP completo [RESPONSÁVEL pode reordenar]

| Versão | Conteúdo |
|---|---|
| **0.36.0 — Fundação** | etapas 1–3 (documentos); Fase A (perfil IES, ativação, licença com assentos, vínculos com escopo, área acadêmica e contexto, convites acadêmicos, avaliador externo); Fase B (campus, curso, período, componente, oferta; importação com prévia; exportação segura); telas; testes negativos de isolamento |
| 0.37.0 — Extensão | Fases C e D: ações de extensão, equipes, horas, entregas com pedido de ajuste, evidências acadêmicas com acesso aplicado, dossiê do estudante e do grupo, retorno da comunidade por link/QR |
| 0.38.0 — Continuidade | Fase E e painel (F parcial): ciclos, passagem de bastão, comparabilidade, painel institucional com indicadores definidos, exportação acadêmica |
| 0.39.0 — Integrações | catálogo de conectores com status honesto, contrato normalizado, mock rotulado "simulado", painel de importação/exportação/sincronização/migração/reconciliação |
| 0.40.0 — Radar de Pesquisa | perfis de pesquisador e grupo, oportunidades com proveniência, match explicável, revisores convidados |

Motivo: o pedido equivale a vários módulos grandes; entregar em fatias com teste e pacote reduz o risco de "tudo pela metade".

## D-13 — Nomes na interface

- Área "Ensino superior" em `/ensino`. "Programa de extensão" sempre com o complemento (a interface já usa "Programa" para edital).

## D-14 — Menores de idade: proteção por padrão

- Calouros podem ter 16–17 anos (LGPD art. 14; Lei 15.211/2025). Para TODO estudante: perfil acadêmico não público, sem
  geolocalização, sem perfilamento para publicidade, retorno da comunidade nunca identifica estudante. A plataforma **não guarda data
  de nascimento**; a IES informa por oferta se pode haver menores, o que reforça os avisos. Validação jurídica: **[IES]**.

## D-15 — Governo, empresas e OSCs não ganham acesso acadêmico

- Parceiro vê só a ação compartilhada com a sua organização e só o necessário (sem notas, horas individuais ou dossiês). Agregados
  com k-anonimato (mínimo 5 estudantes por célula). Acesso detalhado só por concessão explícita (D-08), com finalidade e trilha.

## D-16 — Radar de Pesquisa reaproveita editais e o motor de match (v0.40.0)

- `calls`/`call_sources` com proveniência ampliada (data de captura ≠ data de verificação, hash de conteúdo, histórico), personas
  `researcher` já existentes, revisores pelo mesmo mecanismo de D-08. Nenhuma integração CAPES/CNPq/FINEP/FAPs/Sucupira presumida;
  fonte sem conexão = "manual". Detalhado na v0.40.0.

## D-17 — Funções privilegiadas novas seguem o endurecimento da v0.35.0

- Toda função SECURITY DEFINER nova termina o `search_path` em `pg_temp`, EXECUTE revogado de PUBLIC e concedido a `impacto_app`,
  tabelas só-inclusão com gatilho contra UPDATE/DELETE/TRUNCATE (DB-03/05/07).
