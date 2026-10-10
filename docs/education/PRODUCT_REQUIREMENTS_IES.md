# Requisitos de produto — camada IES (Etapa 2)

Cada requisito tem: tipo (**L** legal com fonte · **O** orientação oficial · **C** regra configurável pela IES · **P** recomendação
de produto · **H** hipótese comercial), versão-alvo e **critério verificável** (o teste que prova). Fontes: `RESEARCH_REGISTER_IES.md`.
Decisões: `DECISIONS_IES.md`. Nenhum requisito promete conformidade, aprovação regulatória ou impacto.

## A. Instituição, licença e acesso (v0.36.0)

| ID | Requisito | Tipo | Critério verificável |
|---|---|---|---|
| RF-A1 | A dona de uma organização `osc`, `company` ou `government` pede o perfil IES informando nome, sigla e categoria administrativa (declarada) | P (D-01) | pedido criado em `requested`; organização `individual`/`provider` recebe 403 |
| RF-A2 | Pessoa da equipe com `admin.organizations.write` ativa ou recusa o perfil, com motivo e identidade confirmada; quem pediu não decide | P | sem step-up → 401 `step_up_required`; decisão registrada na trilha; sem permissão → 403 |
| RF-A3 | Licença institucional: assentos de estudante, validade, origem (contrato, convênio, voucher, cortesia) e referência; **sem preço e sem cobrança**; proposta por uma pessoa com `billing.write`, ativada por outra | H (D-04; ADR-341; ADR-063) | nenhuma coluna de valor; origem `contract` exige referência; quem propôs não ativa; revogação com motivo |
| RF-A4 | Assento consumido quando o estudante ativa o vínculo; sem assento, o vínculo fica "aguardando assento" | H | 2 assentos, 3 estudantes aceitam → 2 ativos e 1 `pending_seat`; nada apagado |
| RF-A5 | Licença vencida não aceita novas ativações e **não** bloqueia leitura/exportação | H (ADR-381) | após o vencimento: aceite novo recusa ativação; estudante ativo continua lendo a própria turma |
| RF-A6 | Vínculos acadêmicos com escopo: gestão acadêmica (instituição), coordenação (curso), docência (oferta), estudante (oferta) | P (D-02) | um usuário com 2 papéis em 2 escopos vê a união, nunca mais |
| RF-A7 | Administração da IES = dona/administradora da organização; estudante e docente **não** viram membros da organização | P (D-02) | estudante não lê projetos, documentos nem finanças da organização IES (teste de muro) |
| RF-A8 | Convite acadêmico por e-mail, token de uso único, 7 dias, revogável; aceite exige conta com o MESMO e-mail confirmado | P | reuso → 409; expirado → 410; revogado → 410; e-mail diferente → 403 |
| RF-A9 | Pessoa com vínculo acadêmico e sem organização usa a área `/ensino`; quem tem os dois escolhe o contexto | P (adendo login §4) | `dashboard_for` → `/ensino` para quem só tem vínculo acadêmico |
| RF-A10 | Avaliador externo autorizado: convite com finalidade, escopo, validade ≤ 90 dias, revogação, somente leitura, leitura registrada; **nunca** rótulo MEC | P (D-08) | após vencer ou revogar → 403; tentativa de escrita → 403; cada leitura gera linha no registro de acesso |
| RF-A11 | A IES declara por entidade a fonte de verdade (planilha/sistema acadêmico × IMPACTO) | C (D-07) | entidade com fonte "IMPACTO": importação não sobrescreve, marca conflito |
| RF-A12 | Padrões protetivos para todo estudante; oferta indica se pode ter menores | L (LGPD art. 14; Lei 15.211/2025) a validar | nenhum dado de estudante em rota pública; nenhum campo de data de nascimento |

## B. Estrutura acadêmica, importação e exportação (v0.36.0)

| ID | Requisito | Tipo | Critério verificável |
|---|---|---|---|
| RF-B1 | Campus, curso (nível, modalidade, carga horária total), período letivo, componente curricular (carga e horas de extensão curricularizada), oferta/turma | P | CRUD com validação; estados; identificadores externos únicos por instituição |
| RF-B2 | Percentual mínimo de extensão por curso, padrão 10%, editável, com a fonte | L (Res. 7/2018 art. 4º) + C | curso mostra carga mínima de extensão = total × percentual; texto "conferir PPC e norma vigente" |
| RF-B3 | Parâmetros do Parecer 576/2023 (parte remota, faixa 10–12%) só como campos opcionais | C (F-02, não homologado) | campos vazios por padrão; nenhuma regra aplicada |
| RF-B4 | Importação CSV/XLSX de cursos, componentes, períodos, ofertas e pessoas/vínculos com **prévia** (criar/atualizar/sem mudança/conflito/rejeitar) e erro por linha | P (D-06) | prévia não grava nada nas tabelas acadêmicas; contagens batem com o arquivo |
| RF-B5 | Aplicar a prévia exige pessoa autorizada; é transacional e idempotente (mesmo arquivo = mesma importação) | P | reenviar o mesmo arquivo devolve a mesma importação; aplicar duas vezes → 409 |
| RF-B6 | Importação de pessoas cria **roteiro + convite**, nunca conta | P (ADR-093) | nenhuma linha nova em `users` após aplicar |
| RF-B7 | Trancamento, cancelamento, transferência e conclusão mudam o **estado** do vínculo; nada é apagado | P (D-07) | após importar "cancelado", o vínculo existe com estado `cancelled` e perde o acesso à turma |
| RF-B8 | Exportação CSV/JSON da estrutura e do roteiro minimizado, com neutralização de fórmula por função única | P (BASELINE §4) | célula iniciada por `= + - @`, TAB ou CR sai neutralizada; cabeçalho também |
| RF-B9 | Relatório de erros da importação baixável | P | CSV com linha, campo e motivo; neutralizado |

## C a E. Extensão, evidências, dossiê, continuidade (v0.37.0–0.38.0) — resumo

| ID | Requisito | Tipo | Versão |
|---|---|---|---|
| RF-C1 | Ação de extensão com modalidade do art. 8º e comunidade externa obrigatória | L (Res. 7/2018 arts. 7º–8º) | 0.37.0 |
| RF-C2 | Equipes, papéis e contribuição individual | P | 0.37.0 |
| RF-C3 | Horas: registro → submetido → aprovado/devolvido/recusado → exportado; quem registra não aprova | P (D-09) | 0.37.0 |
| RF-C4 | Entregas com pedido de ajuste e versões | P | 0.37.0 |
| RF-C5 | Triagem ética que encaminha ao CEP/instância da IES; nunca decide dispensa | O (F-06) | 0.37.0 |
| RF-C6 | Retorno da comunidade por link/QR sem conta, coleta mínima, anti-robô, sem identificar estudante | P | 0.37.0 |
| RF-D1 | Evidência acadêmica com autoria, método, base, acesso aplicado no banco e retenção | L (LGPD arts. 6º, 46) | 0.37.0 |
| RF-D2 | Dossiê do estudante e do grupo com proveniência, pendências e itens não validados | P | 0.37.0 |
| RF-E1 | Ciclo por período e passagem de bastão revisada e aceita; histórico só por inclusão | P (D-11) | 0.38.0 |
| RF-E2 | Painel com indicadores definidos (definição, fonte, período, limitação), k ≥ 5 | P (D-15) | 0.38.0 |

## F. Integrações e G. Radar de Pesquisa (v0.39.0–0.40.0) — resumo

| ID | Requisito | Tipo | Versão |
|---|---|---|---|
| RF-F1 | Catálogo de sistemas com os 6 status (não avaliado … produção ativa); só "produção ativa" com evidência e responsável | P (adendo ERP) | 0.39.0 |
| RF-F2 | Contrato normalizado + mock rotulado "simulado"; nenhum sistema dado como conectado sem teste autorizado | P | 0.39.0 |
| RF-F3 | Migração com backup, mapeamento, dry-run, reconciliação, aprovação e rollback | P | 0.39.0 |
| RF-G1 | Perfis de pesquisador e grupo; oportunidades com fonte, data de captura e aviso; match explicável | P (D-16) | 0.40.0 |

## Requisitos não funcionais (todas as versões)

| ID | Requisito | Critério |
|---|---|---|
| RNF-1 | Autorização no servidor E no banco (RLS) | teste com o ID de outra IES devolve 0 linhas no banco e 403/404 na API |
| RNF-2 | Nenhum segredo, nenhum dado real de pessoa em código, teste ou pacote | `secrets_scan.py`; fixtures marcadas como sintéticas |
| RNF-3 | Logs sem e-mail, matrícula ou token | redator de logs da v0.35.0 aplicado; teste |
| RNF-4 | Acessibilidade: rótulos, teclado, foco, estados vazio/erro/negado | `A11Y_JS` nas telas novas; axe-core com trava no CI |
| RNF-5 | Migração só para frente; funciona do zero e por atualização (inclusive no desenho do Supabase) | teste de banco novo + `test_v0240_managed_db` |
| RNF-6 | Retenção declarada para cada tabela nova | `config/data_retention.json` + teste de cobertura existente |
