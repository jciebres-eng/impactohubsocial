-- 0015 — v0.15.0: índice para cada chave estrangeira que a aplicação usa como CAMINHO DE ACESSO.
-- ACHADO (scripts/db_integrity_report.py, DATABASE_INTEGRITY_REPORT.md): 92 colunas de chave estrangeira em
-- `org_id`/`project_id`/`application_id`/`solution_id`/`call_id`/`diagnosis_id`/`template_id`/`connection_id`/
-- `course_id`/`agreement_id`/`milestone_id` não tinham índice COMEÇANDO por elas. Índice que tem a coluna no meio
-- não serve nem para o filtro do inquilino (toda política de RLS compara `org_id = app_org()`) nem para o
-- ON DELETE CASCADE do pai — nos dois casos o banco varre a tabela inteira.
-- REGRA aplicada: só as colunas acima, que são chave de inquilino ou de pai percorrido pela aplicação. Chave para
-- `users` (created_by, reviewed_by, approved_by…) NÃO entra: a aplicação não lista "tudo que a pessoa X criou", e
-- índice que ninguém usa é custo de escrita sem retorno.
-- Nenhuma destas linhas muda comportamento; todas são IF NOT EXISTS.

CREATE INDEX IF NOT EXISTS ix_fk_agreement_members_org_id ON agreement_members(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_applications_call_id ON applications(call_id);
CREATE INDEX IF NOT EXISTS ix_fk_budget_items_org_id ON budget_items(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_campaigns_org_id ON campaigns(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_commitments_application_id ON commitments(application_id);
CREATE INDEX IF NOT EXISTS ix_fk_commitments_milestone_id ON commitments(milestone_id);
CREATE INDEX IF NOT EXISTS ix_fk_compliance_reviews_org_id ON compliance_reviews(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_conflict_declarations_org_id ON conflict_declarations(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_contribution_models_org_id ON contribution_models(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_contribution_models_project_id ON contribution_models(project_id);
CREATE INDEX IF NOT EXISTS ix_fk_course_certificates_course_id ON course_certificates(course_id);
CREATE INDEX IF NOT EXISTS ix_fk_course_certificates_org_id ON course_certificates(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_course_enrollments_org_id ON course_enrollments(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_course_lessons_course_id ON course_lessons(course_id);
CREATE INDEX IF NOT EXISTS ix_fk_credential_verifications_org_id ON credential_verifications(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_demo_requests_org_id ON demo_requests(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_diagnoses_project_id ON diagnoses(project_id);
CREATE INDEX IF NOT EXISTS ix_fk_diagnosis_actions_org_id ON diagnosis_actions(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_diagnosis_actions_project_id ON diagnosis_actions(project_id);
CREATE INDEX IF NOT EXISTS ix_fk_diagnosis_progress_org_id ON diagnosis_progress(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_diagnosis_versions_org_id ON diagnosis_versions(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_document_assemblies_application_id ON document_assemblies(application_id);
CREATE INDEX IF NOT EXISTS ix_fk_document_assemblies_diagnosis_id ON document_assemblies(diagnosis_id);
CREATE INDEX IF NOT EXISTS ix_fk_document_assemblies_template_id ON document_assemblies(template_id);
CREATE INDEX IF NOT EXISTS ix_fk_documents_application_id ON documents(application_id);
CREATE INDEX IF NOT EXISTS ix_fk_drafts_application_id ON drafts(application_id);
CREATE INDEX IF NOT EXISTS ix_fk_drafts_project_id ON drafts(project_id);
CREATE INDEX IF NOT EXISTS ix_fk_entitlement_grants_agreement_id ON entitlement_grants(agreement_id);
CREATE INDEX IF NOT EXISTS ix_fk_evidences_application_id ON evidences(application_id);
CREATE INDEX IF NOT EXISTS ix_fk_evidences_milestone_id ON evidences(milestone_id);
CREATE INDEX IF NOT EXISTS ix_fk_evidences_org_id ON evidences(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_expenses_milestone_id ON expenses(milestone_id);
CREATE INDEX IF NOT EXISTS ix_fk_expenses_org_id ON expenses(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_favorites_project_id ON favorites(project_id);
CREATE INDEX IF NOT EXISTS ix_fk_feedbacks_application_id ON feedbacks(application_id);
CREATE INDEX IF NOT EXISTS ix_fk_funding_quotas_org_id ON funding_quotas(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_hub_event_registrations_org_id ON hub_event_registrations(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_impact_edges_org_id ON impact_edges(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_impact_nodes_org_id ON impact_nodes(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_impact_tags_org_id ON impact_tags(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_indicator_catalog_org_id ON indicator_catalog(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_indicator_values_org_id ON indicator_values(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_indicator_values_project_id ON indicator_values(project_id);
CREATE INDEX IF NOT EXISTS ix_fk_integration_imports_connection_id ON integration_imports(connection_id);
CREATE INDEX IF NOT EXISTS ix_fk_integration_subscriptions_connection_id ON integration_subscriptions(connection_id);
CREATE INDEX IF NOT EXISTS ix_fk_kb_checklist_progress_org_id ON kb_checklist_progress(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_kb_checklist_progress_project_id ON kb_checklist_progress(project_id);
CREATE INDEX IF NOT EXISTS ix_fk_kb_feedback_org_id ON kb_feedback(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_ledger_entries_org_id ON ledger_entries(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_lesson_progress_course_id ON lesson_progress(course_id);
CREATE INDEX IF NOT EXISTS ix_fk_match_feedback_org_id ON match_feedback(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_match_runs_call_id ON match_runs(call_id);
CREATE INDEX IF NOT EXISTS ix_fk_match_runs_project_id ON match_runs(project_id);
CREATE INDEX IF NOT EXISTS ix_fk_materials_org_id ON materials(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_milestones_org_id ON milestones(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_partnership_requests_org_id ON partnership_requests(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_payment_records_project_id ON payment_records(project_id);
CREATE INDEX IF NOT EXISTS ix_fk_procurement_requests_org_id ON procurement_requests(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_project_indicators_org_id ON project_indicators(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_project_needs_org_id ON project_needs(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_project_needs_project_id ON project_needs(project_id);
CREATE INDEX IF NOT EXISTS ix_fk_project_ods_targets_org_id ON project_ods_targets(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_project_risks_org_id ON project_risks(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_project_snapshots_org_id ON project_snapshots(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_project_transitions_org_id ON project_transitions(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_quota_pledges_project_id ON quota_pledges(project_id);
CREATE INDEX IF NOT EXISTS ix_fk_quotations_org_id ON quotations(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_risk_signals_project_id ON risk_signals(project_id);
CREATE INDEX IF NOT EXISTS ix_fk_saved_search_hits_call_id ON saved_search_hits(call_id);
CREATE INDEX IF NOT EXISTS ix_fk_saved_search_hits_org_id ON saved_search_hits(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_sessions_org_id ON sessions(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_signature_revocations_org_id ON signature_revocations(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_signed_agreement_milestones_org_id ON signed_agreement_milestones(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_signed_agreements_project_id ON signed_agreements(project_id);
CREATE INDEX IF NOT EXISTS ix_fk_solution_adaptations_org_id ON solution_adaptations(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_solution_adaptations_solution_id ON solution_adaptations(solution_id);
CREATE INDEX IF NOT EXISTS ix_fk_solution_combinations_org_id ON solution_combinations(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_solution_disputes_solution_id ON solution_disputes(solution_id);
CREATE INDEX IF NOT EXISTS ix_fk_solution_events_org_id ON solution_events(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_solution_evidence_org_id ON solution_evidence(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_solution_intents_org_id ON solution_intents(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_solution_people_org_id ON solution_people(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_solution_results_solution_id ON solution_results(solution_id);
CREATE INDEX IF NOT EXISTS ix_fk_solution_reviews_org_id ON solution_reviews(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_solution_saves_org_id ON solution_saves(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_solution_saves_solution_id ON solution_saves(solution_id);
CREATE INDEX IF NOT EXISTS ix_fk_solution_search_log_org_id ON solution_search_log(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_solutions_project_id ON solutions(project_id);
CREATE INDEX IF NOT EXISTS ix_fk_support_tickets_org_id ON support_tickets(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_trial_claims_org_id ON trial_claims(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_trust_events_org_id ON trust_events(org_id);
CREATE INDEX IF NOT EXISTS ix_fk_voucher_redemptions_org_id ON voucher_redemptions(org_id);
