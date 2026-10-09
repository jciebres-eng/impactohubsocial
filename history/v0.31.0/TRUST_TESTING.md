# TRUST_TESTING — o que está provado por teste (v0.14.0)

Suíte da camada: `backend/tests/test_v0140_trust.py` (**88 testes**) + `backend/tests/test_e2e_v0140_trust.py`
(**8 testes de navegador**). Suíte completa do projeto: **564 testes, 0 falhas**
(evidência: `docs/evidence/test_run_v0.14.0.log`).

```
cd backend && TEST_ADMIN_DATABASE_URL="postgresql://postgres@127.0.0.1:5432/postgres" \
  PASSWORD_SCRYPT_N=16384 RATE_LIMIT_MULTIPLIER=1000 python3 -m unittest discover -s tests -t . -v
```
Cada execução cria um banco vazio e aplica **todas** as 12 migrações: a migração é testada em banco vazio em toda rodada.

## Cobertura por área
| Classe | Testes | O que prova |
|---|---|---|
| `TwoLayerSignature` | 7 | sem código não assina · código errado · senha errada antes do código · sucesso com as duas camadas · uso único · morre quando o conteúdo muda · SMS recusa explicitamente |
| `PublicVerification` | 10 | terceiro verifica sem login · **nenhum dado pessoal no corpo** · código tolerante a digitação errada · código inexistente e malformado · **arquivo adulterado é detectado** · revogação aparece · outra organização não revoga · nova versão substitui e a antiga continua verificável dizendo isso · QR servido · contador de acesso |
| `CustodyChain` | 4 | a cadeia registra cada fato e o encadeamento confere (`prev_hash` do primeiro é zero; cada um aponta o anterior) · **nem a organização nem o contexto de sistema reescrevem** · adulteração (como dono do banco) é detectada no `seq` exato · integridade do arquivo detecta troca e registra `integrity_failed` |
| `SignatureRevocation` | 2 | revogada aparece como revogada e **continua no histórico** · outra organização não revoga |
| `IdentityVerification` | 5 | nível inicial e catálogo · biometria e telefone **recusam com 501** · documento exige decisão humana · autopromoção bloqueada no banco · a assinatura guarda o nível |
| `ProfessionalCredential` | 5 | catálogo honesto (20 conselhos, `number_pattern` nulo) · nasce autodeclarada · documento + decisão humana verifica e eleva a identidade · revogação registrada · conselho exige UF |
| `SignedAgreements` | 8 | publicar exige 2 partes obrigatórias · jornada completa com 2 assinaturas → vigente → código público com 2 signatários · não assina duas vezes · quem não é parte **nem pede o código** · recusa cancela · rascunho não gera código público · hash congelado e uma parte não marca a outra · acompanhamento longitudinal · as duas partes veem, estranho não vê |
| `TrustTenantIsolation` | 5 | registros, custódia, integridade e identidade isolados entre organizações |
| `TrustConcurrency` | 2 | **4 assinaturas simultâneas com o mesmo código ⇒ 1** · 4 criações simultâneas de código público ⇒ 1 registro ativo |
| `TaxonomyAndTags` | 4 | 17 ODS com cores oficiais e aviso sobre os emblemas da ONU · marcação funciona · **código inventado é recusado pelo banco** · marcador idempotente e removível |
| `LocalesAndTheme` | 5 | cobertura declarada por idioma · **catálogo completo e com as mesmas chaves nos 3 idiomas** · filtro por namespace · idioma desconhecido 404 · preferências de ida e volta |
| `FundingQuotas` | 7 | matemática das cotas e quantas faltam · **não vende além do total** · **4 reservas simultâneas não estouram** · não apoia o próprio projeto · não confirma o próprio pagamento · campanha pública mostra quantas faltam e só quando publicada · slug único entre organizações |
| `FeeTablesAndServices` | 6 | tabela nasce vazia e diz isso · **publicar sem fonte é recusado** · publicar com fonte funciona · tabela publicada não é editada · catálogo de atividades e card do diretório · **geo só é pública com consentimento registrado** |
| `GuidedDiagnosis` | 6 | roteiro com progresso real · concluir exige as respostas obrigatórias · salvar parcial não exige tudo · etapa com documento obrigatório exige o documento · pular registra o motivo · etapa inexistente e documento de outra organização recusados |
| `DocumentFormats` | 10 | docx/xlsx/odt/ods reabertos e **XML conferido** · tipos de célula corretos (texto, número, booleano) · ODF com `mimetype` primeiro e sem compressão · nomes de tag saneados no XML · PDF com QR · **ida e volta do QR pelo nosso pipeline** · exportação do dataset nos **8 formatos** · neutralização de fórmula · exportação do rascunho em 3 formatos com QR opcional · WOPI declarado não implementado |
| `TimestampsAndRfc3161` | 2 | carimbo interno aplicado e **conferível pelo selo** · RFC 3161 **recusa em vez de fingir** |
| `TrustE2E` (navegador) | 8 | terceiro verifica sem login e **sem ver dado pessoal** · revogação na tela · código inexistente com mensagem amigável · registro público na interface · tema escolhido aplicado antes do primeiro render e persistente · **contraste AA no tema escuro manual** · campanha pública com "Faltam 6 cotas" · 7 telas novas sem erro de console, com 1 `<h1>` e sem IDs duplicados |

## O que NÃO está testado (honestidade)
- **Nenhuma assinatura qualificada** (ICP-Brasil/gov.br) — não existe para testar.
- **Nenhum provedor de biometria, SMS ou ACT** — o que existe é a recusa explícita, e **essa** está testada.
- **Nenhum leitor de QR comercial** leu o código neste ambiente. O que foi provado é a ida e volta no nosso próprio
  pipeline (encode → matriz → decode dos códigos de dados) mais a conferência estrutural (padrões de posição,
  temporização, módulo escuro, informação de formato legível).
- **Nenhum arquivo foi aberto no Microsoft Office ou no LibreOffice** neste ambiente. O que foi provado é que o ZIP
  reabre, o XML é válido e os tipos de célula estão corretos.
- Carga e volume de produção.
- `npm audit` / `pip-audit`: registros bloqueados no ambiente.
- Pentest.
