"""Comandos operacionais.

python -m impacto.cli create-admin --email ops@empresa.com --name "Fulano"   # senha lida do stdin (nunca por argumento)
python -m impacto.cli seed-demo                                              # SOMENTE development/test
python -m impacto.cli kb-import --author-email ops@empresa.com             # conteúdo inicial como RASCUNHO (demo), para revisão editorial
python -m impacto.cli gen-secrets                                            # gera valores para SECRET_KEY etc. (não grava nada)
python -m impacto.cli legal-list                                             # situação das minutas jurídicas, com o id de cada uma
python -m impacto.cli legal-approve --doc-key terms_of_use --reviewed-by "Fulana, OAB/MT 1234" --review-reference "Parecer 12/2026"
"""
from __future__ import annotations

import argparse
import getpass
import json
import secrets
import sys

from .security.crypto import generate_key


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="impacto")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("create-admin")
    a.add_argument("--email", required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--promote-existing", action="store_true",
                   help="promove uma conta JÁ existente (troca a senha pela informada e encerra as sessões dela)")
    sub.add_parser("seed-demo")
    k = sub.add_parser("kb-import", help="importa o conteúdo inicial da Central como RASCUNHOS (demo) para revisão editorial")
    k.add_argument("--author-email", required=True)
    sub.add_parser("gen-secrets")
    # APROVAÇÃO JURÍDICA PELA LINHA DE COMANDO, e o motivo de existir está escrito aqui.
    #
    # Em produção o cadastro responde 503 `legal_documents_not_published` até que `terms_of_use` e
    # `privacy_policy` estejam aprovados — isso é desenho, não defeito. Mas a rota de aprovação
    # exige `doc_id`, e NENHUMA rota, tela ou documento expunha esse id: `legal_overview()` devolve
    # doc_key, título, versão e situação, e não o id. O operador ficava sem saída a não ser abrir o
    # banco com psql no dia da publicação — exatamente quando ninguém quer improvisar com SQL.
    #
    # Isto NÃO é atalho para aprovar sem revisão: chama a mesma `services.legal.approve`, que exige
    # revisor nomeado e referência da revisão, e o CHECK do banco exige também. O que muda é só o
    # caminho até o id.
    sub.add_parser("legal-list", help="situação das minutas jurídicas, com o id de cada uma")
    la = sub.add_parser("legal-approve", help="aprova uma minuta (exige revisor nomeado e referência)")
    la.add_argument("--doc-key", required=True, help="ex.: terms_of_use, privacy_policy")
    la.add_argument("--reviewed-by", required=True, help="quem assume a revisão (nome e registro)")
    la.add_argument("--review-reference", required=True, help="parecer, processo ou contrato que embasa")
    la.add_argument("--effective-from", default=None, help="AAAA-MM-DD (padrão: hoje)")
    args = p.parse_args(argv)

    if args.cmd == "gen-secrets":
        print(f"SECRET_KEY={secrets.token_urlsafe(48)}")
        print(f"VOUCHER_HMAC_KEY={secrets.token_urlsafe(48)}")
        print(f"FIELD_ENCRYPTION_KEY={generate_key()}")
        print(f"METRICS_TOKEN={secrets.token_urlsafe(32)}")
        return 0

    from .app import AppState
    from .config import load_settings
    from .db.pool import DbContext
    from .security import passwords
    state = AppState(load_settings())

    if args.cmd == "seed-demo":
        if state.settings.env not in ("development", "test"):
            print("Recusado: seed de demonstração só em development/test", file=sys.stderr)
            return 1
        from .seed_dev import seed
        print(seed(state, force=True))
        return 0

    if args.cmd == "kb-import":
        from .services import kb_seed
        with state.pool.tx(DbContext(system=True)) as c:
            uid = c.scalar("SELECT id::text FROM users WHERE email = $1", args.author_email.lower())
            if not uid:
                print("Autor não encontrado", file=sys.stderr)
                return 1
            print(kb_seed.import_seed(c, author_id=uid, reviewer_id=None, publish=False))
        print("Itens criados como RASCUNHO (demo). A publicação exige revisão de outra pessoa no CMS.")
        return 0

    if args.cmd == "create-admin":
        pw = sys.stdin.readline().rstrip("\n") if not sys.stdin.isatty() else getpass.getpass("Senha do administrador: ")
        probs = passwords.password_problems(pw, args.email)
        if probs or len(pw) < 14:
            print("Senha fraca (mínimo 14 caracteres para administradores): " + "; ".join(probs), file=sys.stderr)
            return 1
        with state.pool.tx(DbContext(system=True)) as c:
            org = c.scalar("SELECT id::text FROM organizations WHERE kind = 'platform' LIMIT 1")
            if not org:
                org = c.scalar("INSERT INTO organizations(kind, legal_name, compliance_status) VALUES ('platform','Administração da Plataforma','approved')"
                               " RETURNING id::text")
            # v0.35.0 (auditoria, AUTH-04): antes, um e-mail já cadastrado era promovido a administrador MANTENDO a senha que
            # tinha — quem cadastrasse antes o e-mail do futuro administrador entrava como administrador. Agora conta
            # existente é recusada; com --promote-existing, a senha passa a ser a informada aqui e as sessões são encerradas.
            existente = c.one("SELECT id::text AS id FROM users WHERE email = $1", args.email.lower())
            if existente and not args.promote_existing:
                print("Já existe uma conta com este e-mail. Para promovê-la (a senha passa a ser a informada agora e as sessões"
                      " dela são encerradas), repita com --promote-existing.", file=sys.stderr)
                return 1
            if existente:
                uid = existente["id"]
                c.run("UPDATE users SET is_platform_admin = true, password_hash = $2, failed_login_count = 0, locked_until = NULL,"
                      " mfa_enabled_at = NULL, mfa_secret_enc = NULL, mfa_recovery_hashes = '{}', mfa_last_counter = NULL WHERE id = $1",
                      uid, passwords.hash_password(pw))
                c.run("UPDATE sessions SET revoked_at = now(), revoke_reason = 'promoted_to_admin' WHERE user_id = $1 AND revoked_at IS NULL", uid)
            else:
                uid = c.scalar("INSERT INTO users(email, full_name, password_hash, is_platform_admin, email_verified_at) VALUES ($1,$2,$3,true, now())"
                               " RETURNING id::text", args.email.lower(), args.name, passwords.hash_password(pw))
            c.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'owner') ON CONFLICT DO NOTHING", uid, org)
            # `$2` DUAS VEZES COM TIPOS DIFERENTES NÃO FUNCIONA.
            #
            # `actor_user_id` é `uuid` e `object_id` é `text`. Repetindo `$2` nos dois, o PostgreSQL
            # tenta deduzir um tipo só para o parâmetro e recusa: "inconsistent types deduced for
            # parameter $2". A transação inteira era desfeita — sem organização da plataforma, sem
            # usuário, sem membership. Ou seja: `create-admin` NUNCA funcionou num banco limpo, que
            # é exatamente onde ele é usado.
            #
            # Não aparecia porque desenvolvimento usa o administrador que vem do `seed-demo`, e
            # nenhum teste rodava o CLI. `test_v0231_cli.py` passa a rodar.
            c.run("INSERT INTO audit_events(org_id, actor_user_id, action, object_type, object_id, payload)"
                  " VALUES ($1,$2::uuid,'admin.created','user',$3::text,'{}')", org, uid, uid)
        print(f"Administrador criado: {args.email}. No primeiro login, ative o MFA (obrigatório para a área administrativa).")
        return 0

    if args.cmd == "legal-list":
        from .services import legal as LEGAL
        with state.pool.tx(DbContext(system=True), readonly=True) as c:
            linhas = c.query("SELECT id::text AS id, doc_key, title, version, status, requires_acceptance"
                             " FROM legal_documents ORDER BY doc_key, version DESC")
            visao = LEGAL.overview(c)
        print(f"{'doc_key':22s} {'versão':>6s}  {'situação':18s} {'aceite':6s}  id")
        for r in linhas:
            print(f"{r['doc_key']:22s} {r['version']:>6d}  {r['status']:18s} "
                  f"{'SIM' if r['requires_acceptance'] else '-':6s}  {r['id']}")
        bloqueando = visao["blocking_product"]
        print()
        if bloqueando:
            print(f"BLOQUEANDO O PRODUTO ({len(bloqueando)}): {', '.join(bloqueando)}")
            print("Enquanto houver documento nesta lista, o cadastro responde 503 "
                  "`legal_documents_not_published`. Isso é desenho, não defeito.")
        else:
            print("Nenhum documento bloqueando o produto.")
        return 0

    if args.cmd == "legal-approve":
        from .services import legal as LEGAL
        with state.pool.tx(DbContext(system=True)) as c:
            doc = c.one("SELECT id::text AS id, doc_key, version, status FROM legal_documents"
                        " WHERE doc_key = $1 ORDER BY version DESC LIMIT 1", args.doc_key)
            if not doc:
                print(f"Minuta não encontrada: {args.doc_key}. Use `legal-list` para ver as chaves.",
                      file=sys.stderr)
                return 2
            try:
                r = LEGAL.approve(c, doc_id=doc["id"], reviewed_by=args.reviewed_by,
                                  review_reference=args.review_reference,
                                  effective_from=args.effective_from)
            except Exception as exc:  # noqa: BLE001 - a mensagem precisa chegar legível ao operador
                print(f"Não foi possível aprovar {args.doc_key}: {exc}", file=sys.stderr)
                return 2
            c.run("INSERT INTO audit_events(org_id, actor_user_id, action, object_type, object_id, payload)"
                  " VALUES (NULL,NULL,'legal.approved','legal_document',$1::text,$2::jsonb)",
                  doc["id"], json.dumps({"doc_key": args.doc_key, "version": doc["version"],
                                         "reviewed_by": args.reviewed_by,
                                         "review_reference": args.review_reference,
                                         "via": "cli"}, ensure_ascii=False))
        print(f"Aprovado: {r['doc_key']} v{r['version']} · vigente desde {r['effective_from']} "
              f"· revisão de {r['reviewed_by']}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
