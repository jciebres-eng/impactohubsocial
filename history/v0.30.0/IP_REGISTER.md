# Registro de propriedade intelectual — v0.7.0

Isto é um **inventário técnico**, não parecer jurídico. Nada aqui concede ou garante titularidade. **[VALIDAR com advogado de PI]**

| Ativo | Natureza | Titular esperado | Situação / ação |
|---|---|---|---|
| Código-fonte (`backend/`, `web/src`, `scripts/`, `infra/`, testes) | PRÓPRIO — obra de software (Lei 9.609/98) | proprietário do projeto | gerado com assistência de IA (Claude) a pedido do proprietário; **definir licença do repositório e registrar titularidade**; se houver contribuidores/desenvolvedores, **cessão de direitos patrimoniais por escrito**. Registro de programa de computador no INPI é opcional. |
| Esquema SQL, migrações, OpenAPI | PRÓPRIO | idem | |
| Regras de negócio, pesos do match, taxonomia, prompts, workflows | PRÓPRIO — segredo empresarial | idem | versionados em `config/`; **não alegar patente**; pesos são hipóteses, não "algoritmo patenteável" |
| Nome "Impacto", identidade visual (paleta, "Trilha"), ícone | PRÓPRIO (provisório) | idem | **busca de anterioridade e registro de marca no INPI pendentes**; nome pode colidir com marcas existentes |
| Documentação e minutas legais | PRÓPRIO (minuta) | idem | revisão jurídica obrigatória antes de publicar |
| Componentes open source | OSS | respectivos autores | ver `THIRD_PARTY_DEPENDENCIES.md`; licenças permissivas; manter avisos de copyright |
| Fontes Lora e Inter | ASSET OFL | autores | redistribuição permitida com a licença; não vender as fontes isoladamente |
| Relatório-fonte (PDF atribuído a Manus AI) e prompts do proprietário | conteúdo de terceiros / do proprietário | **a confirmar** | `history/v0.6.0/sources/`; confirmar direitos de redistribuição antes de abrir o repositório |
| Dados de OSCs, empresas, profissionais | dados dos titulares | cada titular | licença limitada ao serviço; portabilidade (`/v1/privacy/export`) |
| Dados demonstrativos | FICTÍCIO | — | marcados "[EXEMPLO FICTÍCIO]"/`is_example`; CNPJs sintéticos válidos só no formato; **não usar fora do dev** |
| Domínio, cloud, chaves, contas de lojas, certificados | contas externas | proprietário (em nome da organização) | MFA, dois administradores, cofre de segredos; **não existem ainda** |

## Riscos de PI identificados
1. Marca não pesquisada. 2. Direitos do PDF-fonte. 3. Conteúdo gerado por IA: titularidade/proteção autoral de obras com forte contribuição de IA é matéria em evolução — documentar a direção humana (briefings, decisões, revisões). 4. Termos dos provedores de IA/APIs (uso de saída, dados enviados). 5. Dados de terceiros importados de editais públicos: respeitar termos das fontes e citar a origem (`url` oficial é obrigatória em editais externos).

## Contratos recomendados
Desenvolvimento/contribuição com **cessão expressa**, entrega de código, credenciais e pipelines; NDA; contrato com profissionais parceiros (responsabilidade técnica, sigilo, LGPD operador/controlador); DPA com provedores.
