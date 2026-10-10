# Jornadas dos usuários — camada IES

Uma conta por pessoa, login central (`/entrar`), e depois o servidor decide para onde levar (`/portal` → `dashboard_for`). Quem tem
vários vínculos troca de contexto pelo menu ou por `/portal?escolher=1`. Ninguém escolhe papel na tela de login.

## J1 — A IES entra na plataforma (v0.36.0)

1. A dona de uma organização (OSC, empresa ou órgão público) abre **Ensino superior → Ativar** e pede o perfil IES: nome, sigla,
   categoria administrativa (declarada; a plataforma não certifica).
2. Uma pessoa da equipe de conformidade (`admin.organizations.write`) confere e ativa (ou recusa com motivo), confirmando a identidade.
3. A equipe concede a licença: uma pessoa propõe (assentos de estudante, validade, origem e referência do contrato) e **outra** ativa.
   Nenhum valor aparece.
4. A administração da IES define a fonte de verdade por entidade e cria (ou importa) campus, cursos, períodos, componentes e ofertas.

**Estados de erro:** organização de tipo não permitido → explicação e caminho; pedido em análise → aviso; recusado → motivo.

## J2 — Importar a estrutura e o roteiro (v0.36.0)

1. Administração (ou gestão acadêmica) envia um CSV/XLSX e escolhe a entidade.
2. A tela mostra a **prévia**: quantas linhas seriam criadas, atualizadas, sem mudança, em conflito ou recusadas, com o erro de cada
   linha. Nada foi gravado.
3. Quem tem permissão confirma; a aplicação é atômica. Reenviar o mesmo arquivo mostra a mesma importação.
4. Pessoas importadas viram **entradas de roteiro com convite**; ninguém ganha conta sem aceitar.

**Erros:** arquivo inválido, colunas faltando, linha com erro (o resto aparece, mas a aplicação só leva as válidas e o relatório
lista as recusadas), arquivo grande demais.

## J3 — Estudante (v0.36.0; ampliada na v0.37.0)

1. Recebe o convite no e-mail institucional → abre o link → entra (ou cria conta com o MESMO e-mail) → aceita.
2. Cai em **/ensino**: as próprias turmas, a situação do assento ("ativo" ou "aguardando assento"), o que está incluído pela
   instituição e o aviso de que nenhuma operação de IA acadêmica está ligada nesta versão.
3. Vê só os próprios dados. Na v0.37.0: equipe, ações, horas, entregas, evidências e dossiê.

**Erros:** convite vencido/revogado/já usado → mensagem e caminho ("peça um novo convite à sua coordenação"); e-mail diferente →
"este convite é para outro e-mail" sem revelar qual; turma de outra IES → negado.

## J4 — Docente (v0.36.0; ampliada na v0.37.0)

1. Aceita o convite; vê **as próprias ofertas** e o roteiro de cada uma.
2. Não vê outras turmas da IES nem as de outra IES. Na v0.37.0: revisa horas e entregas (nunca as próprias).

## J5 — Coordenação de curso (v0.36.0)

1. Vê as ofertas e o roteiro dos cursos do escopo; inclui docente e estudante nessas ofertas; emite convites.
2. Não vê outros cursos, nem dados financeiros/documentais da organização IES.

## J6 — Avaliador externo autorizado (v0.36.0)

1. A administração da IES concede acesso: e-mail, finalidade, escopo e validade (até 90 dias).
2. A pessoa aceita com conta própria e vê, só para leitura, a estrutura e os agregados do escopo. Cada leitura fica registrada.
3. No vencimento ou na revogação, o acesso termina na hora. A tela nunca diz "MEC", "Inep" ou "oficial".

## J7 — Parceiro, governo, empresa (todas as versões)

- Participar do ecossistema **não** dá acesso a nada acadêmico. Na v0.37.0, o parceiro vê apenas a ação compartilhada com a sua
  organização e responde ao retorno por link/QR sem conta.

## J8 — Equipe da plataforma (v0.36.0)

- Ativa perfis (conformidade) e concede licenças (cobrança, quatro olhos), sempre com confirmação de identidade e trilha. Não navega em
  dados acadêmicos de rotina.

## Mapa de redirecionamento depois do login

| Vínculos | Para onde vai |
|---|---|
| só equipe da plataforma | painel da equipe (inalterado) |
| organização (com ou sem vínculo acadêmico) | início da organização; "Ensino superior" no menu e em `/portal?escolher=1` |
| só vínculo acadêmico e/ou acesso de avaliador | `/ensino` |
| nenhum vínculo | criar organização **ou** aceitar convite acadêmico pendente |
