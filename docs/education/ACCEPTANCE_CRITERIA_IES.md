# Critérios de aceite — camada IES

Uma versão só é chamada de entregue se cada critério dela tiver teste executado (PASSOU) ou estiver declarado BLOQUEADO com causa.
Nada de "conforme ao MEC", "LGPD garantida", "integração concluída" ou "impacto comprovado".

## v0.36.0 — Fundação

| # | Critério | Como se prova |
|---|---|---|
| AC-01 | A IES tem espaço institucional isolado: administração de uma IES não lê nem escreve nada de outra (porta e muro) | teste HTTP + consulta no banco com o contexto da IES A e o ID da IES B → 0 linhas |
| AC-02 | Perfil IES só para osc/company/government; ativação por equipe com permissão, identidade confirmada e trilha; licença com quatro olhos | testes 403/401/200 + evento de auditoria; quem propôs a licença não ativa |
| AC-03 | Licença sem preço; assento por estudante; sem assento → aguardando; vencida → não ativa novos e não bloqueia leitura | testes de assento e de vencimento |
| AC-04 | Estudante não é membro da organização e não lê projetos/documentos/finanças dela | teste de muro em tabelas da organização |
| AC-05 | Estudante vê só a própria turma e só a si mesmo no roteiro; tentar rota de docente/coordenação → negado | testes negativos (adendo §8.8) |
| AC-06 | Docente vê só as próprias ofertas; coordenação só o próprio curso | testes negativos (adendo §8.9–10) |
| AC-07 | Convite: válido aceita; expirado, revogado e reutilizado recusam; e-mail diferente recusa | 5 testes |
| AC-08 | Ninguém altera o próprio papel/escopo pelo corpo da requisição | teste com campos extras → 422 e sem efeito |
| AC-09 | Avaliador: leitura no escopo; escrita negada; após vencer/revogar → negado; leitura registrada | testes + linhas no registro de acesso |
| AC-10 | Importação: prévia sem gravação; contagens corretas; arquivo inválido sem gravação parcial; aplicar é atômico e idempotente; pessoas viram roteiro+convite sem criar conta | testes com arquivos sintéticos |
| AC-11 | Fonte de verdade "IMPACTO" faz a importação marcar conflito em vez de sobrescrever | teste |
| AC-12 | Cancelamento/trancamento muda estado e corta o acesso à turma; nada é apagado | teste |
| AC-13 | Exportação neutraliza fórmula (células e cabeçalhos; `= + - @`, TAB, CR) | teste da função única + teste da rota |
| AC-14 | Quem só tem vínculo acadêmico entra em `/ensino` sem precisar criar organização | teste de `dashboard_for` + E2E no navegador |
| AC-15 | Telas novas: rótulos, `h1` único, estados vazio/erro/negado; sem erro de console | `A11Y_JS` no Chromium; axe-core com trava no CI |
| AC-16 | Migração aplica do zero e por atualização (inclusive desenho do Supabase); retenção declarada para as tabelas novas | testes existentes de migração/retenção passando com a 0075 |
| AC-17 | Regressão: suíte completa e jornadas existentes sem falha nova não explicada | log da regressão + CI do PR |
| AC-18 | Nenhum texto/rota com "MEC", "Inep", "CAPES" sugerindo acesso ou integração oficial | teste de varredura nos textos da interface |

## v0.37.0 — v0.40.0

Critérios da lista do kit (jornadas E2E 5–22) distribuídos por versão em `PRODUCT_REQUIREMENTS_IES.md`; cada versão terá a sua
tabela aqui, preenchida antes da implementação dela.
