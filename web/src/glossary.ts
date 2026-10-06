// GERADO por scripts/sync_glossary.py a partir de config/glossary.json — não edite à mão.
// Rótulos em pt-BR (idioma de origem). Para en/es, use GET /v1/public/glossary?locale=...
// ou GET /v1/public/translations (namespaces g_*), que já caem para pt-BR quando falta chave.

export const GLOSSARY_VERSION = "1.0";

export const CLAIM_KIND: Record<string, string> = {
  "result": "resultado",
  "ods_contribution": "contribuição a ODS",
  "esg": "ASG",
  "environmental": "ambiental",
  "social": "social",
  "governance": "governança",
  "efficiency": "eficiência",
  "financial": "financeira",
  "comparative": "comparativa",
  "certification": "certificação",
};

export const CLAIM_REVIEW_DECISION: Record<string, string> = {
  "accepted": "aceita",
  "needs_change": "pede alteração",
  "rejected": "recusada",
};

export const CLAIM_SEVERITY: Record<string, string> = {
  "info": "informação",
  "attention": "atenção",
  "serious": "grave",
};

export const CLAIM_STATUS: Record<string, string> = {
  "unchecked": "não verificada",
  "substantiated": "sustentada pelo que está registrado",
  "attention": "pontos de atenção",
  "flagged": "marcada — exige revisão humana de outra organização",
  "flagged_accepted_by_review": "marcada e aceita em revisão, com a marca mantida",
  "needs_change": "revisão pediu alteração",
  "rejected_by_review": "recusada em revisão",
  "withdrawn": "retirada por quem a declarou",
};

export const CONFIDENCE_BAND: Record<string, string> = {
  "high": "confiança alta",
  "medium": "confiança média",
  "low": "confiança baixa — trate como indício",
  "insufficient_data": "dados insuficientes — não é recomendação",
  "insufficient": "dados insuficientes — não é recomendação",
};

export const DATA_AVAILABILITY: Record<string, string> = {
  "known": "informado",
  "unknown": "não informado",
  "unavailable": "indisponível",
  "not_applicable": "não se aplica",
};

export const EQUITY_DENOMINATOR: Record<string, string> = {
  "eligible_population": "população elegível",
  "reference_population": "população de referência",
  "households": "domicílios",
  "enrolled": "matrículas ou cadastros",
  "area_km2": "área em km²",
  "service_units": "unidades de serviço",
  "resource_cents": "recurso aplicado",
};

export const EQUITY_METHOD: Record<string, string> = {
  "per_eligible_population": "por 1.000 pessoas da população elegível declarada",
  "per_reference_population": "por 1.000 pessoas da população de referência do território",
  "per_household": "por 1.000 domicílios",
  "per_enrolled": "por 100 matrículas ou cadastros do serviço",
  "per_area_km2": "por km² do território",
  "per_service_unit": "por unidade de serviço existente no território",
  "per_resource": "por R$ 1.000 aplicados",
};

export const EQUITY_STANDING: Record<string, string> = {
  "declared": "declarada",
  "documented": "documentada (documento no cofre ou fonte citada com data)",
  "evidenced": "evidenciada (evidência registrada)",
};

export const EVIDENCE_SOURCE: Record<string, string> = {
  "absent": "ausente",
  "declared": "declarada pela organização",
  "inferred": "inferida pela plataforma",
  "platform_record": "registro da plataforma",
  "official_catalog": "catálogo oficial",
  "signed_document": "documento assinado",
  "verified_document": "documento verificado",
  "verified_credential": "credencial verificada",
  "validated_measurement": "medição validada",
};

export const FRAMEWORK_LENS: Record<string, string> = {
  "impact_only": "só impacto — quanto a organização afeta o mundo",
  "financial_only": "só financeira — quanto o tema afeta a organização",
  "double": "dupla materialidade — os dois eixos",
};

export const FRAMEWORK_RELATION: Record<string, string> = {
  "aligned": "alinhado — o indicador conversa com o referencial, sem conferência",
  "mapped": "mapeado — há correspondência declarada com um código do referencial",
  "assessed": "avaliado — alguém analisou a correspondência e registrou a análise",
  "reported": "relatado — o número foi publicado citando o referencial, com fonte",
  "verified": "verificado — conferido por revisor de OUTRA organização",
  "audited": "auditado — conferido por auditoria independente, com registro",
};

export const MATCH_SIGNAL: Record<string, string> = {
  "cause": "causa",
  "territory": "território",
  "budget": "orçamento",
  "readiness": "prontidão",
  "ods": "ODS",
  "deadline": "prazo",
  "history": "histórico",
  "ods_esg": "ODS e ASG",
  "capacity": "capacidade",
  "evidence_history": "histórico de evidência",
  "impact": "impacto",
  "urgency": "urgência",
  "preference": "preferência",
};

export const READINESS: Record<string, string> = {
  "project_readiness": "prontidão do projeto",
  "organization_readiness": "prontidão da organização",
  "funding_readiness": "prontidão para captar",
  "evidence_readiness": "prontidão de evidência",
  "compliance_readiness": "prontidão de conformidade",
  "data_readiness": "prontidão de dado",
  "governance_readiness": "prontidão de governança",
  "impact_readiness": "prontidão de impacto",
};

export const READINESS_STATUS: Record<string, string> = {
  "ready": "pronto",
  "needs_review": "precisa de revisão",
  "unknown": "desconhecido",
};

export const REPUTATION_BAND: Record<string, string> = {
  "high": "confiança alta",
  "medium": "confiança média",
  "low": "confiança baixa — trate como indício",
  "insufficient": "dados insuficientes — não é recomendação",
  "insufficient_data": "dados insuficientes — não é recomendação",
};

export const REPUTATION_DISPUTE_OUTCOME: Record<string, string> = {
  "corrected": "corrigido",
  "partially_corrected": "corrigido em parte",
  "no_change": "sem alteração",
  "needs_more_information": "falta informação",
};

export const RESPONSIBILITY_SCOPE: Record<string, string> = {
  "organization": "organização",
  "program": "programa",
  "project": "projeto",
  "document": "documento",
};

export const SEAL_DEFINITION_STATUS: Record<string, string> = {
  "draft": "rascunho",
  "published": "publicada",
  "retired": "aposentada",
};

export const SEAL_REVOCATION_REASON: Record<string, string> = {
  "criterion_no_longer_met": "critério deixou de ser satisfeito",
  "definition_retired": "definição aposentada",
  "data_correction": "correção de dado",
  "request_of_holder": "pedido de quem recebeu",
  "misconduct": "conduta",
};

export const SEAL_SCOPE: Record<string, string> = {
  "organization": "organização",
  "project": "projeto",
};

export const SEAL_STATUS: Record<string, string> = {
  "active": "ativo",
  "expired": "expirado",
  "revoked": "revogado",
  "superseded_definition": "definição superada por versão nova",
  "definition_retired": "definição aposentada",
};

export const SUGGESTION_ORIGIN: Record<string, string> = {
  "official_load": "carga oficial (com fonte e data)",
  "platform_knowledge": "conhecimento da plataforma — conferir na carga oficial",
  "platform_editorial": "lista editorial da plataforma",
  "your_organization": "histórico da sua organização",
  "another_organization": "declarado por outra organização",
};

/** Rótulo oficial de um termo. Sem rótulo, devolve a própria chave — nunca inventa sinônimo. */
export function term(domain: Record<string, string>, key: string | null | undefined): string {
  if (!key) return "não informado";
  return domain[key] ?? key;
}
