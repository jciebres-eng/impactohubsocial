# Modelo de dados da camada IES — v0.36.0 (migração `0075_v0360_education_foundation.sql`)

Princípios: toda tabela tem dono inequívoco (`institution_id` = a organização IES), chaves estrangeiras **compostas** que impedem ligar
registros de IES diferentes, estados por CHECK, RLS habilitada, GRANT mínimo a `impacto_app`, funções privilegiadas com
`search_path` terminado em `pg_temp` e EXECUTE só para a aplicação (D-17). Nada é apagado por importação; desligamento é estado.

## Tabelas

| Tabela | Para quê | Chaves e restrições principais | Retenção |
|---|---|---|---|
| `academic_institutions` | perfil IES de uma organização | PK `org_id` → `organizations`; categoria administrativa declarada; estado `requested/active/rejected/suspended`; quem decide ≠ quem pediu; colunas de decisão protegidas (`guard_columns`) | enquanto a organização existir |
| `academic_licenses` | licença institucional sem preço | assentos > 0; validade; origem `contract/convention/voucher/courtesy` (contrato exige referência); `proposed → active → revoked`; quem ativa ≠ quem propôs; só equipe escreve | histórico permanente (comercial) |
| `academic_campuses` | campus | único por nome e por ID externo na IES | com a IES |
| `academic_courses` | curso | nível, modalidade, carga horária total, **% mínimo de extensão (padrão 10, editável) com fonte**, parâmetros opcionais do Parecer 576/2023; único por ID externo | com a IES |
| `academic_periods` | período letivo | código único na IES; datas coerentes; `planned/open/closed` | com a IES |
| `academic_components` | componente curricular | FK composta (curso, IES); horas de extensão ≤ carga | com a IES |
| `academic_offerings` | oferta/turma | FK compostas (componente, IES) e (período, IES); `may_have_minors` (padrão **verdadeiro** — o mais protetivo); `planned/active/closed/cancelled` | com a IES |
| `academic_people` | roteiro: quem a IES declarou | ID institucional, e-mail institucional, nome de exibição; `user_id` só depois do aceite (SET NULL se a conta for excluída); sem CPF, sem nascimento | com a IES; anonimizável |
| `academic_roles` | vínculo acadêmico com escopo | papel × escopo coerentes por CHECK (`academic_manager`→`organization`; `coordinator`→`academic_course`; `teacher`/`student`→`academic_offering`); escopo validado por gatilho como da MESMA IES; estado `active/pending_seat/suspended/ended`; situação de matrícula (estudante): `enrolled/locked/cancelled/transferred/completed`; assento (`license_id`); um vínculo vivo por (pessoa, papel, escopo) | histórico permanente; fim com motivo |
| `academic_invitations` | convite acadêmico | token só como hash; 7 dias; aceito/revogado uma vez (gatilho) | 180 dias após encerrar |
| `academic_access_grants` | avaliador externo autorizado | finalidade (≥ 20 caracteres); escopo; validade ≤ 90 dias; só leitura; revogação com motivo | 5 anos (prova de quem teve acesso) |
| `academic_access_log` | o que o avaliador leu/exportou | só inclusão (gatilho contra UPDATE/DELETE/TRUNCATE) | junto com a concessão |
| `academic_imports` | importação com prévia | idempotência (IES, entidade, SHA-256 do arquivo); `previewed/applied/discarded/rejected`; contagens; `purge_after` | metadados permanentes |
| `academic_import_rows` | linhas da prévia | dados **já normalizados e mínimos**; ação `create/update/unchanged/conflict/reject`; erros; `target_kind` + `target_id` (catálogo polimórfico) | **dados das linhas apagados 30 dias** após criar (rotina `edu_retention`) |

## Funções de acesso (SECURITY DEFINER, `STABLE`, sem efeito colateral)

| Função | Verdadeira quando a pessoa da sessão (`app_uid()`)… |
|---|---|
| `edu_is_admin(inst)` | é dona/administradora da organização da IES, a organização está ativa e o perfil IES está **ativo** |
| `edu_is_manager(inst)` | `edu_is_admin` **ou** tem vínculo ativo `academic_manager` na IES |
| `edu_coordinates(course)` | gestão da IES do curso **ou** coordenação ativa do curso |
| `edu_teaches(offering)` | coordenação do curso da oferta **ou** docência ativa na oferta |
| `edu_enrolled(offering)` | vínculo de estudante ativo **e** matrícula `enrolled` na oferta |
| `edu_grant_covers(inst, tipo, id)` | tem concessão de avaliador aceita, vigente e não revogada que cobre o alvo |
| `edu_member(inst)` | qualquer um dos anteriores na IES |
| `edu_person_visible(person)` | gestão; a própria pessoa; docente/coordenação de uma oferta/curso onde a pessoa tem vínculo vivo |

## Regras no banco (o muro, além da porta)

- Estrutura (campus, curso, período, componente, oferta): leitura por `edu_member` da IES; escrita por gestão (e coordenação para as
  ofertas do próprio curso).
- Pessoas e vínculos: leitura por `edu_person_visible`; escrita por gestão/coordenação no escopo; **ninguém** altera o próprio vínculo
  (gatilho recusa quando a pessoa do vínculo é a da sessão, exceto o aceite feito pela função de aceite).
- Licença: leitura por gestão; escrita só equipe (`app_priv()`).
- Dados pessoais acadêmicos **não** são lidos pela equipe da plataforma por padrão: as políticas usam `app_system()` (rotinas) e não
  `app_priv()`.
- Trilha: eventos `edu.*` podem ser gravados na cadeia da IES por quem é `edu_member` dela (política nova, aditiva).
- Aceite de convite e de concessão por funções próprias (`edu_accept_invitation`, `edu_accept_grant`) que conferem token (hash),
  validade, revogação, uso único e **o e-mail confirmado da conta** — e alocam assento.

## Migração, atualização e reversão

- Só acrescenta tabelas, funções, políticas e uma natureza jurídica alterada (`academic_institution` passa a aceitar
  `osc/company/government`). Nenhuma coluna existente muda de tipo; nenhum dado existente é tocado.
- Aplicada do zero e por atualização; testada no desenho do Supabase (`test_v0240_managed_db`).
- Reversão: código anterior convive com as tabelas novas (ninguém as lê). Desfazer a migração não é previsto (padrão da casa:
  só para frente); para desligar a camada basta não publicar o código.
