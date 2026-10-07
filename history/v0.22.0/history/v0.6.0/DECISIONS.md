# Registro de decisões (ADR) — v0.1
Formato: contexto → decisão → consequência. Status: Aceita (provisória até confirmação) | Aberta.

| # | Decisão | Motivo | Status |
|---|---|---|---|
| 001 | Núcleo = SaaS B2B de gestão de grants/programas; "Tinder" vira modo opcional de triagem sobre shortlist | Relatório Manus; swipe não melhora decisão de comprador corporativo | Aceita (confirmar) |
| 002 | Web responsiva + PWA primeiro; Android/iOS só com necessidade demonstrada (offline, câmera, push) | Custo de lojas, duplicação de fluxo | Aceita (confirmar) |
| 003 | Sem custódia/split/pagamento de aportes no MVP; só registro de compromisso | Risco regulatório | Aceita |
| 004 | Cobrança de **assinaturas da própria plataforma** via gateway externo, desacoplado; ativada só após parecer [VALIDAR] | Plataforma será vendida | Aceita |
| 005 | Modular monolith TypeScript (NestJS ou equivalente), PostgreSQL, S3-compatível; sem Redis/Elastic/microserviços de início | Simplicidade | Aceita |
| 006 | Multi-tenant por `tenant_id` + RLS + autorização por objeto | Isolamento | Aceita |
| 007 | **Escalonamento/posição/nível/selo de prestador não é produto vendável**; níveis só por verificação de evidência | Pedido do proprietário + integridade | Aceita (confirmar interpretação) |
| 008 | Invariante: nenhum plano/voucher altera elegibilidade, score ou ordenação do match | Confiança/independência | Aceita |
| 009 | Premium de OSC/Prestador modelado, mas desligado por flag no piloto; OSC gratuita no início | Relatório Manus (não cobrar OSC antes de provar valor) | Aceita (confirmar) |
| 010 | Vouchers: códigos aleatórios, armazenados como hash, resgate atômico, dupla aprovação para gratuidade acima de limiar | Anti-fraude | Aceita |
| 011 | Fiscal: apenas "mecanismo possível a validar" + fontes versionadas + revisão humana; sem cálculo de economia | Risco fiscal | Aceita |
| 012 | Ledger = trilha encadeada por hash em PostgreSQL; sem blockchain | Sem justificativa técnica | Aceita |
| 013 | Pesos do match = configuração por programa (padrão do relatório), não constantes | São hipóteses | Aceita |
| 014 | Provedor de IA atrás de interface; IA nunca aprova, assina ou decide elegibilidade | Responsabilidade | Aceita |
| 015 | Escolha de cloud, gateway, IdP, nome/marca | Dependem do proprietário | Aberta |
