# Dependências de terceiros (candidatas — nenhuma instalada)

| Categoria | Candidata | Substituto | Licença/risco |
|---|---|---|---|
| Linguagem/framework | TypeScript, NestJS, React | Fastify, Vue | verificar versões e licenças no SBOM |
| Banco | PostgreSQL | — | PostgreSQL License |
| Storage | S3-compatível | outro S3 | contrato/região |
| IdP | provedor OIDC (a escolher) | outro | exportação de usuários |
| Billing | gateway (**a escolher**) | via `BillingProvider` | conformidade/regulatório [VALIDAR] |
| IA/OCR | provedor (a escolher) | via `AiProvider` | retenção/treino [VALIDAR] |
| E-mail/push | a escolher | via `Notifier` | opt-in |
| KYB/listas | opcional | — | cobertura/falso positivo |
| Lojas | Apple/Google | — | políticas atuais |

Versões e licenças exatas ficam para o primeiro SBOM (gerado do código). Nenhum fornecedor foi decidido.
