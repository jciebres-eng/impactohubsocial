# Modelo do Terceiro Setor — v0.10.0

A plataforma separa **cinco camadas** que costumam ser confundidas. Cada uma tem dono, fonte e regra de verdade próprios.

| Camada | O que é | Onde vive | Quem define |
|---|---|---|---|
| 1. Natureza jurídica | O que a organização **é** (associação, fundação, cooperativa, coletivo, empresa…) | `organizations.legal_nature_code` → catálogo `legal_nature` | A organização **declara**; a administração pode conferir |
| 2. Qualificações / certificações | Títulos concedidos por terceiros (OSC/MROSC, OSCIP, OS, CEBAS, utilidade pública…) | `organization_qualifications` (+ eventos) | Organização declara; **só a administração marca "verificada"** |
| 3. Perfil de atuação | Como a organização atua/financia (proponente, financiador, apoiador…) | `organizations.institutional_profile` | Organização |
| 4. Situação institucional | Estado da organização na plataforma (ex.: regular, parcialmente regular, em análise) | `organizations.institutional_status` | **Decisão humana justificada** da administração (`suggest_status` apenas sugere) |
| 5. Elegibilidade calculada | Resultado **por oportunidade**, não por organização | `eligibility_evaluations` | Motor determinístico; nunca editável à mão |

## Regras de verdade
- **Declarado ≠ verificado.** Toda qualificação nasce `declared`. Para `verified` exige: autoridade emissora, número/protocolo, documento validado **ou** URL de consulta, vigência não vencida e justificativa. Há histórico em `organization_qualification_events` (leitura por RLS; escrita só por contexto privilegiado).
- **Sem dados, sem nota.** Maturidade, prontidão e badges só mostram "sem dados" quando faltam fatos.
- **Desconhecido nunca vira "sim".** Resposta padrão: *"Não foi possível confirmar."*
- **Catálogos iniciais são classificação da plataforma**, marcados `needs_professional_validation`: não são parecer jurídico.
- **Coletivos sem CNPJ** podem se cadastrar (natureza `collective`) e participar do que não exige CNPJ; modalidades que exigem CNPJ aparecem como requisito não atendido, com orientação.

## Maturidade institucional 0–6
Calculada por `engines/institutional/maturity.py` a partir de `config/institutional_maturity.json` (**hipótese inicial a calibrar**). Níveis: 0 ideia/iniciativa · 1 coletivo em estruturação · 2 proponente formalizado · 3 organização formal regular · 4 com qualificações/certificações · 5 apta a certas modalidades · 6 histórico comprovado. A saída traz, em três listas: *Pode participar*, *Pode receber este tipo específico de recurso* e *Ainda precisa cumprir requisitos*, cada item com o motivo.

## Documentos institucionais
Cinco estados exibidos com estes rótulos: **AUSENTE, PENDENTE DE VALIDAÇÃO, VALIDADO, EXPIRADO, REJEITADO**. Upload aprovado no antivírus ≠ validado; a validação é ato humano (`/v1/admin/institutional/documents/{id}/validate`).

## Badges
Calculados (nunca estáticos), com critério, fonte, data de verificação e validade. Aviso obrigatório: **classificação interna da plataforma, não certificação governamental**.

## Limites (o que NÃO fazemos)
Não consultamos bases governamentais em tempo real; não emitimos certidões; não garantimos elegibilidade, captação ou benefício fiscal; não substituímos assessoria jurídica/contábil.
