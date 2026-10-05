# Produto

## Problema
Financiadores têm custo alto para estruturar critérios, triar, verificar e acompanhar iniciativas; OSCs repetem cadastros e prestações de contas; prestadores têm dificuldade de ser encontrados no contexto certo.

## Papéis e quem paga
| Papel | Usa | Paga | Nota |
|---|---|---|---|
| Empresa / Instituto / Fundação | Programas, chamadas, triagem, aprovação, relatórios | **Sim** (assinatura anual + implantação) | Comprador principal |
| OSC | Perfil reutilizável, oportunidades, documentos, evidências | Gratuito no piloto; premium opcional (flag) | Voucher aplicável |
| Prestador | Perfil, convites, propostas, entregas | Gratuito; premium opcional (flag) | Posição nunca é paga |
| Revisor / Compliance | Parecer, conflito, trilha | Via tenant do financiador | |
| Admin da plataforma | Operação, regras, vouchers, suporte | — | Acesso a conteúdo sensível só excepcional e auditado |
| Beneficiário final | Não tem conta no MVP | — | |

## Jornada OSC
Perfil → documentos (com validade) → oportunidade/necessidade (ex.: 10 violões × R$ 500 = R$ 5.000) → fracionamento em tranches → submissão → pendências → compromisso → execução → evidências → prestação de contas.
Cada dado tem origem: **autodeclarado / extraído (rascunho) / verificado por fonte / revisado por pessoa**.

## Jornada Empresa
Onboarding (objetivos, causas, território, orçamento, políticas, restrições) → programa/chamada → critérios versionados → shortlist explicada → comparação → pedido de esclarecimento → aprovação (com conflito declarado) → compromisso (fora da plataforma) → acompanhamento → relatório.

## Jornada Prestador
Perfil opt-in (serviços, território, credenciais com estado de verificação) → recebe convite/demanda de projeto → proposta → seleção pelo contratante → contrato direto fora da plataforma → tarefas/entregas → assinatura do profissional → aceite.

## Workflow de compliance
Cadastro → Validação → Análise → Aprovação → Match → Interesse → Due Diligence → Compromisso → Execução → Prestação de contas. Cada transição gera `audit_event`.

## Descoberta (substitui o swipe como centro)
Lista pesquisável + shortlist comparável. Modo "triagem rápida" (swipe) é opcional sobre a shortlist; ação = salvar / descartar com motivo / pedir esclarecimento. **Cada card responde:** o que é; quanto custa; por que combina; impacto esperado (meta, não promessa); risco; está documentado (estado e validade); o que acontece depois.

## Necessidades e fracionamento
Projeto-mãe + tranches (valor mínimo/meta, prazo, escopo, orçamento, marco). Soma de compromissos ≤ orçamento elegível. Fracionar **não** torna parcela elegível a incentivo fiscal.

## Fora do escopo do MVP
App nativo, pagamento/custódia/split, scoring de pessoas, selo de impacto, ranking público de OSC, blockchain, OCR sem revisão, IA fiscal autônoma, comparativos entre clientes, voluntariado, API pública sem autorização, multi-país.

## Métricas de produto (a medir)
Tempo para shortlist; % candidaturas com documentos completos; tempo de resposta da OSC; decisões que pediram revisão fiscal/legal; projetos que chegam à 1ª entrega; retrabalho por relatório; conversão voucher→assinatura paga.
