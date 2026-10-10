"""LGPD — direitos do titular: acesso/portabilidade (export), eliminação/anonimização, consentimentos; textos legais."""
from __future__ import annotations

import uuid

from starlette.responses import Response

from ..core import access as ACCESS
from ..http import ApiError, Ctx, json_response, route
from . import schemas as S

T = ("privacy",)


@route("GET", "/v1/privacy/export", auth="user", raw=True, rate=("export_ip", 10, 3600), tags=T,
       summary="Exporta os dados pessoais do titular em JSON (art. 18, II e V da LGPD)")
def export(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        data = {
            "user": c.one("SELECT id::text AS id, email::text AS email, full_name, email_verified_at, status, locale, created_at, last_login_at,"
                          " mfa_enabled_at IS NOT NULL AS mfa_enabled FROM users WHERE id = $1", ctx.user_id),
            "memberships": c.query("SELECT o.legal_name, o.kind, m.role, m.created_at FROM memberships m JOIN organizations o ON o.id = m.org_id"
                                   " WHERE m.user_id = $1", ctx.user_id),
            "consents": c.query("SELECT kind, version, granted, at FROM consents WHERE user_id = $1 ORDER BY at", ctx.user_id),
            "sessions": c.query("SELECT created_at, last_seen_at, ip, user_agent, revoked_at FROM sessions WHERE user_id = $1 ORDER BY created_at DESC"
                                " LIMIT 200", ctx.user_id),
            "privacy_requests": c.query("SELECT kind, status, created_at, completed_at FROM privacy_requests WHERE user_id = $1", ctx.user_id),
            # v0.17.0: a prova de aceite é dado do titular e tem de sair na portabilidade. Vai com o
            # hash do texto aceito, que é o que torna a prova verificável por quem recebe o arquivo.
            "legal_acceptances": c.query("SELECT doc_key, version, body_sha256, accepted_at, source, ip, user_agent"
                                         " FROM legal_acceptances WHERE user_id = $1 ORDER BY accepted_at", ctx.user_id),
        }
    with ctx.system_tx() as c:
        data["activity"] = c.query("SELECT action, object_type, at, ip FROM audit_events WHERE actor_user_id = $1 ORDER BY id DESC LIMIT 1000", ctx.user_id)
        c.run("INSERT INTO privacy_requests(user_id, kind, status, completed_at) VALUES ($1,'export','completed', now())", ctx.user_id)
        ctx.audit(c, "privacy.export", "user", ctx.user_id)
    resp = json_response(data)
    resp.headers["Content-Disposition"] = 'attachment; filename="meus-dados-impacto.json"'
    return resp


class DeleteIn(S.In):
    password: str
    confirm: bool


@route("POST", "/v1/privacy/delete-account", auth="user", body=DeleteIn, raw=True, rate=("delete_ip", 5, 3600), tags=T,
       summary="Elimina a conta: anonimiza dados pessoais e revoga sessões. Registros financeiros/auditoria são mantidos pseudonimizados (obrigação legal).")
def delete_account(ctx: Ctx, body: DeleteIn):
    if not body.confirm:
        raise ApiError(422, "confirmation_required", "Confirme a exclusão")
    # v0.22.0 — UMA implementação de confirmação de identidade (core/access.py). Eram três cópias,
    # cada uma conferindo a senha no próprio handler; três cópias de uma regra de segurança
    # divergem na primeira vez que alguém endurece uma e esquece as outras. Esta aqui ganhou MFA de
    # brinde: antes, apagar a conta de quem tem segundo fator pedia apenas a senha.
    ACCESS.verify_identity(ctx, password=body.password, mfa_code=getattr(body, "mfa_code", None))
    with ctx.system_tx() as c:
        owned = c.query("SELECT m.org_id::text AS org_id, o.legal_name, (SELECT count(*) FROM memberships x WHERE x.org_id = m.org_id) AS members,"
                        " (SELECT count(*) FROM memberships x WHERE x.org_id = m.org_id AND x.role = 'owner') AS owners,"
                        " (SELECT count(*) FROM commitments cm WHERE cm.osc_org_id = m.org_id OR cm.funder_org_id = m.org_id) AS financial"
                        " FROM memberships m JOIN organizations o ON o.id = m.org_id WHERE m.user_id = $1 AND m.role = 'owner'", ctx.user_id)
        blockers = [o["legal_name"] for o in owned if o["owners"] == 1 and (o["members"] > 1)]
        if blockers:
            raise ApiError(409, "transfer_ownership_first", "Transfira a propriedade das organizações antes de excluir a conta",
                           {"organizations": blockers})
        anon = f"removido-{uuid.uuid4().hex[:12]}@anonimizado.invalid"
        closed = [o["org_id"] for o in owned if o["members"] == 1]
        for oid in closed:
            c.run("UPDATE organizations SET status = 'closed', contact_email = NULL, phone = NULL WHERE id = $1", oid)
        # v0.35.0 (auditoria, FILE-09): os ARQUIVOS pessoais também saem — antes a conta era anonimizada e os documentos de
        # identidade, o documento de dirigente enviado pela pessoa e as exportações de dados ficavam guardados para sempre.
        # Saem: documento anexado a verificação de identidade da pessoa; `documento_dirigente` e `exportacao_dados` que ela
        # enviou ou que foram gerados para a organização que fecha com ela. Ficam (guarda da organização, que é pessoa
        # jurídica e cujos registros servem a terceiros): estatuto, certidões, prestação de contas… e documento ASSINADO.
        personal = c.query(
            "SELECT d.id::text AS id, d.storage_key FROM documents d WHERE d.deleted_at IS NULL"
            " AND NOT EXISTS (SELECT 1 FROM signatures s WHERE s.subject_type = 'document' AND s.subject_id = d.id)"
            " AND (d.id IN (SELECT document_id FROM identity_documents WHERE user_id = $1)"
            "      OR (d.uploaded_by = $1 AND d.doc_type IN ('documento_dirigente', 'exportacao_dados'))"
            "      OR (d.doc_type = 'exportacao_dados' AND d.org_id = ANY($2::uuid[])))", ctx.user_id, closed)
        if personal:
            c.run("UPDATE documents SET deleted_at = now(), extracted_text = NULL WHERE id = ANY($1::uuid[])", [p["id"] for p in personal])
        c.run("DELETE FROM memberships WHERE user_id = $1", ctx.user_id)
        c.run("UPDATE users SET email = $2, full_name = 'Titular removido', password_hash = NULL, mfa_secret_enc = NULL, mfa_enabled_at = NULL,"
              " mfa_recovery_hashes = '{}', oidc_subject = NULL, status = 'deleted' WHERE id = $1", ctx.user_id, anon)
        c.run("UPDATE sessions SET revoked_at = now(), revoke_reason = 'account_deleted', ip = NULL, user_agent = NULL WHERE user_id = $1", ctx.user_id)
        c.run("DELETE FROM auth_tokens WHERE user_id = $1", ctx.user_id)
        # A prova de aceite SOBREVIVE (obrigação legal), sem o IP e sem o agente de usuário. O gatilho
        # `acceptance_anonymize_only()` permite exatamente esta alteração e recusa qualquer outra.
        c.run("UPDATE legal_acceptances SET ip = NULL, user_agent = NULL WHERE user_id = $1", ctx.user_id)
        c.run("INSERT INTO privacy_requests(user_id, kind, status, completed_at, notes) VALUES ($1,'deletion','completed', now(),"
              " 'Dados pessoais anonimizados; registros de auditoria e financeiros mantidos pseudonimizados')", ctx.user_id)
        ctx.audit(c, "privacy.account_deleted", "user", ctx.user_id, {"personal_files_removed": len(personal)})
    for p in personal:   # depois do COMMIT: o registro já diz "excluído"; um objeto que falhe fica no log para nova tentativa
        try:
            ctx.app.storage.delete(p["storage_key"])
        except Exception as exc:  # noqa: BLE001
            import logging

            from ..observability import log
            log(logging.getLogger("impacto.privacy"), logging.ERROR, "personal_file_delete_failed", document_id=p["id"],
                error_type=type(exc).__name__)
    from ..services.auth import clear_session_cookies
    resp = json_response({"deleted": True})
    clear_session_cookies(ctx, resp)
    return resp


class ConsentIn(S.In):
    kind: str
    granted: bool


@route("POST", "/v1/privacy/consents", auth="user", body=ConsentIn, tags=T, summary="Registra/revoga consentimento opcional (ex.: comunicações)")
def consent(ctx: Ctx, body: ConsentIn):
    if body.kind != "marketing":
        raise ApiError(422, "validation_error", "Somente consentimentos opcionais podem ser alterados aqui")
    with ctx.tx() as c:
        c.run("INSERT INTO consents(user_id, kind, version, granted, ip) VALUES ($1,'marketing','v1',$2::bool,$3)", ctx.user_id, body.granted, ctx.ip)
    return {"kind": body.kind, "granted": body.granted}


@route("GET", "/v1/legal/{doc}", auth="none", raw=True, tags=T,
       summary="Texto legal em Markdown, servido do registro versionado (minuta vem marcada como minuta)")
def legal(ctx: Ctx):
    """Serve do registro, não do disco.

    Até a v0.16.0 esta rota lia o arquivo e se chamava "textos legais VIGENTES" — e nenhum deles
    estava vigente. Agora ela serve a mesma linha cujo sha256 um aceite referenciaria, e diz no
    cabeçalho em que situação o documento está.
    """
    from ..services import legal as REG
    with ctx.tx(readonly=True) as c:
        doc = REG.text(c, key=ctx.path["doc"])
    return Response(doc["body_md"], media_type="text/markdown; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=600",
                             "X-Legal-Status": doc["status"],
                             "X-Legal-Version": str(doc["version"]),
                             "X-Legal-Sha256": doc["body_sha256"]})


@route("GET", "/v1/privacy/retention", auth="user", tags=T,
       summary="O que a plataforma guarda, por quanto tempo e o que ela NÃO consegue apagar")
def retention(ctx: Ctx):
    """A política de retenção CONFERIDA contra o banco, não apenas declarada.

    Até a v0.20.0 este motor existia (`core/retention.py`, v0.19.0), produzia a conferência e só
    era alcançável por um script de linha de comando — isto é, a pessoa de quem são os dados não
    tinha como ler. Uma política de retenção que o titular não consegue ler não cumpre a função
    que a justifica.

    O que sai daqui é a classe EFETIVA de cada vínculo, apurada nos gatilhos reais do banco. Quando
    a declaração diverge do que o banco faz, a divergência aparece — e é a declaração que está
    errada, nunca o banco.
    """
    from ..core import retention as RET
    with ctx.tx(readonly=True) as c:
        doc = RET.load()
        conferencia = RET.audit(c, doc)
    return {
        "classes": doc["classes"],
        "audit": conferencia,
        "effective_class_note": doc.get("effective_class_note"),
        "note": ("`append_only` significa que o banco IMPEDE a remoção por gatilho: a plataforma "
                 "não promete apagar o que ela própria bloqueia. Em particular, A PLATAFORMA NÃO "
                 "REMOVE ORGANIZAÇÃO — o vínculo é anonimizado e o registro histórico permanece, "
                 "porque apagá-lo apagaria também a prestação de contas de terceiros."),
    }
