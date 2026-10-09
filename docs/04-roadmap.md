# 04 — Roadmap: próximos incrementos (do mais urgente ao menos urgente)

Cada incremento é pequeno, vai numa branch própria, passa pelo demo antes da produção e termina com teste e registro no
CHANGELOG. "Você" = o responsável pelo projeto; "eu" = o Claude.

## Agora (esta semana)

| # | Incremento | Resolve | Quem faz | Precisa de você? |
|---|---|---|---|---|
| 1 | **Segurança imediata:** trocar o token R2 do backup; publicar a produção (aplica a 0071); conferir os logs do worker (4 documentos "ilegíveis", sem travar) | C2, A1 | você clica, eu guio e confiro | sim — painéis Cloudflare, GitHub e Railway |
| 2 | **Limpar a produção:** tirar as 15 contas e as organizações de demonstração do banco de produção (ou recriá-lo vazio) | C1 | eu preparo, testo no demo e executo | **sim — autorização expressa** (apaga dados) |
| 3 | **CI verde de novo:** atualizar o teste da exceção de RLS (com o motivo escrito), regenerar a matriz de integrações, registrar a v0.30.1 (versão, CHANGELOG, manifesto) | A4, M5 | eu | não (só aprovar o pull request) |
| 4 | **Aviso de demonstração:** faixa fixa no site quando o modo for `development`, e decisão sobre cadastro aberto no demo | M10 | eu | decidir aberto × só convidados |

## Próximas 2 semanas

| # | Incremento | Resolve | Quem faz | Precisa de você? |
|---|---|---|---|---|
| 5 | **Worker com menor privilégio:** trazer da branch `infra/v0.31.0` o `start_worker.sh` (troca para `impacto_app`, espera o banco atualizado, não mexe em senha) e trocar o comando do `pleasing-trust` | A3 | eu (código) + você (comando no Railway) | sim — trocar o comando no painel |
| 6 | **Restauração que funciona:** trazer `managed_backup_restore.sh`, corrigir as instruções do `backup-supabase` e criar o ensaio mensal de restauração de um backup **cifrado** do R2 (num banco descartável, sem exportar nada) | A2, M8 | eu | não |
| 7 | **Domínio próprio** (`www`), redirecionamento, TLS *Full (strict)*, `PUBLIC_BASE_URL`, monitor apontando para o `www` | M2, M1 | você clica, eu guio | sim — Cloudflare e Railway |
| 8 | **E-mail autenticado** (SPF/DKIM do Brevo na Cloudflare; remetente `no-reply@`) | M3 | você clica, eu guio | sim |
| 9 | **Monitor confiável:** se o agendamento do GitHub continuar sem rodar, monitor externo gratuito (UptimeRobot/Better Stack) além do workflow | M1 | você cria a conta, eu configuro o texto | sim |

## Antes de dados reais (bloqueia a abertura ao público)

| # | Incremento | Resolve | Quem faz | Precisa de você? |
|---|---|---|---|---|
| 10 | **Revisão jurídica** dos Termos de Uso e da Política de Privacidade; aprovação registrada com nome e OAB | A5 | advogado(a) + você | sim — nome e OAB do revisor |
| 11 | **Encarregado de dados (DPO)** nomeado e publicado; prazos de retenção por tipo de dado confirmados | A5 | você | sim |
| 12 | **Senha de `impacto_app` igual** no GitHub e no Railway | A6 | você cola no GitHub | sim |
| 13 | **Supabase de Nano para Micro** | M11 | você | sim (custo) |
| 14 | **Primeiro administrador real** com verificação em duas etapas; conferência final com o verificador pós-publicação (`pos-deploy`, da branch `infra/v0.31.0`) | — | você + eu | sim |

## Depois da abertura (melhorias)

| # | Incremento | Resolve |
|---|---|---|
| 15 | Juntar o restante útil da branch `infra/v0.31.0` (validação do R2, teste do armazenamento contra servidor real, `/healthz` mostrando o commit publicado) e encerrar essa branch | M6 |
| 16 | Remover o `deploy.yml` de modelo; documentar o Railway como único caminho | M7 |
| 17 | Investigar os 4 arquivos que sumiram do armazenamento | M4 |
| 18 | Arrumação: documentos antigos para `history/`, ações do GitHub atualizadas, avisos de estilo | B2, B3, B4 |
| 19 | Funcionalidades que dependem de parceiros: pagamentos, nota fiscal, assinatura digital, IA externa — cada uma só com contrato, parecer e teste | — |

## Decisões que dependem de você

1. **Produção com contas de demonstração (C1):** desativar as 15 contas ou recriar o banco de produção vazio?
2. **Demo aberto ou fechado:** qualquer pessoa com o link pode criar conta, ou só convidados?
3. **Repositório público ou privado:** hoje é público — qualquer pessoa lê o código e o `CLAUDE.md` (sem senhas, mas com
   os identificadores dos projetos). Privado reduz exposição; público é gratuito para as rotinas do GitHub e combina
   com transparência. A escolha é sua.
4. **Branch `infra/v0.31.0`:** posso trazê-la em partes (recomendado, itens 5, 6, 15 e 16) ou você prefere descartá-la?
5. **Revisor jurídico:** nome e OAB de quem vai revisar os termos e a política.
