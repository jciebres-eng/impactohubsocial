# Identidade, organização, vínculo, papel, permissão e contexto — camada IES

| Conceito (adendo §2) | Na IMPACTO | Observação |
|---|---|---|
| **Identidade** | `users` (uma conta por pessoa; e-mail único) | a mesma para OSC, empresa, governo, IES, docente, estudante e avaliador |
| **Organização/tenant** | `organizations`; a IES é uma organização com perfil `academic_institutions` (D-01) | mantém o tipo real (`osc`, `company`, `government`) |
| **Vínculo com a organização** | `memberships` (6 papéis) | administração da IES = dona/administradora; **estudante e docente não entram aqui** (D-02) |
| **Vínculo acadêmico** | `academic_people` (quem a IES declarou) + `academic_roles` (papel × escopo × estado) | só vale depois que a pessoa aceita o convite com o mesmo e-mail; a conta não é criada por importação |
| **Papel** | `academic_manager`, `coordinator`, `teacher`, `student` | nome de perfil não é autorização: o servidor e o banco decidem por papel + escopo + estado |
| **Permissão** | funções `edu_*()` no banco + verificação explícita no serviço | ex.: `edu_teaches(oferta)`, `edu_enrolled(oferta)` |
| **Contexto ativo** | organização ativa da sessão (inalterado) **e**, na área `/ensino`, a instituição/oferta escolhida na URL | o ID da URL é **sempre** reconferido no servidor; o navegador não é fonte de verdade |
| **Acesso temporário** | `academic_access_grants` (avaliador externo) | só leitura, escopo, validade ≤ 90 dias, revogação, registro de leitura |

## Regras

1. **Sem conta duplicada:** o convite acadêmico se liga à conta logada que tem o mesmo e-mail confirmado. Quem já tem conta (por
   exemplo, profissional que também leciona) usa a mesma.
2. **Vários vínculos:** uma pessoa pode ser docente numa oferta e coordenadora de um curso, ou estudante numa IES e administradora de
   uma OSC. A interface mostra os contextos; o acesso é a **união** dos escopos ativos, nunca mais.
3. **Sem autoelevação:** ninguém cria, altera ou encerra o próprio vínculo acadêmico (gatilho no banco); papéis nunca vêm do corpo de
   uma requisição de quem os recebe.
4. **Revogação:** encerrar vínculo, cancelar matrícula, revogar convite ou concessão corta o acesso na requisição seguinte (o acesso é
   recalculado a cada requisição; não há cache de permissão).
5. **Separação de suporte e conteúdo:** a equipe da plataforma ativa perfis e licenças; não lê roteiro, vínculos nem prévias de
   importação por padrão (políticas usam o contexto de sistema das rotinas, não o modo administrador).
6. **Menores:** nenhum dado de idade é coletado; padrões protetivos para todo estudante (D-14).
