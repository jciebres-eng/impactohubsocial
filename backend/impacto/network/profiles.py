"""Perfil público em impacto.app/@identificador: página pública que NUNCA lê tabela privada.

REGRA CENTRAL (pedido §47): "a página pública nunca deve ler diretamente tabelas privadas". Aqui isso é estrutura, não
disciplina: existe uma coluna `public_fields` com a PROJEÇÃO curada, montada pelo servidor em
`rebuild_projection()`, e a rota pública lê só essa coluna. Mesmo princípio de `verifiable_records.public_fields`, da
camada de confiança (v0.14.0).

Consequência prática: se amanhã alguém acrescentar uma coluna sensível em `organizations`, ela não aparece na página
pública por descuido — porque a página não consulta `organizations`. Para vazar, alguém teria que escrever a coluna
dentro de `PROJECTABLE` deste arquivo, que é uma lista fechada e revisável.

Anti-impersonação, em três camadas:
  1. `reserved_handles` — @admin, @suporte, @oficial e 22 outros não se registram (gatilho no banco);
  2. `handle_history` — trocar é permitido, apagar o rastro não (append-only);
  3. `verified_badge` — coluna protegida por `guard_columns`: a organização não se verifica a si mesma.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from ..db.pq import Connection, Json
from ..http import ApiError, forbidden, not_found, unprocessable

HANDLE_RE = re.compile(r"^[a-z0-9](?:[a-z0-9_.-]{1,28}[a-z0-9])$")

#: O que PODE entrar na projeção pública. Lista FECHADA: nada chega à página pública sem passar por aqui.
#: Cada entrada é (chave na projeção, de onde vem, exige qual `show_*`).
PROJECTABLE: tuple[tuple[str, str, str | None], ...] = (
    ("display_name", "profile", None),
    ("headline", "profile", None),
    ("bio", "profile", None),
    ("handle", "profile", None),
    ("kind", "org", None),
    ("territory", "org", "show_territory"),
    ("mission", "org", None),
    ("founded_year", "org", None),
    ("causes", "org", None),
    ("ods", "org", None),
    ("projects", "derived", "show_projects"),
    ("impact", "derived", "show_impact_history"),
    ("credentials", "derived", "show_credentials"),
    ("organizations", "derived", "show_organizations"),
    ("contact", "derived", "show_contact"),
    ("links", "profile", None),
    ("verified_badge", "profile", None),
    ("member_since", "derived", None),
)

#: Campos que NUNCA entram, por mais que alguém pergunte. Estão escritos para que o teste possa afirmar a ausência.
NEVER_PUBLIC = ("cnpj", "email", "phone", "address", "document_number", "compliance_status", "compliance_risk",
                "beneficiary_group", "sensitive", "cpf", "birth_date", "bank", "revenue")


def normalize(raw: str) -> str:
    """Normaliza o identificador pedido. Acento sai, maiúscula desce, separador vira ponto.

    POR QUE NORMALIZAR E NÃO SÓ VALIDAR: sem normalização, "Instituto Água" e "instituto-agua" seriam dois perfis
    diferentes, e quem lê "@instituto.agua" não distingue de "@instituto.água". Confusão de identificador é a porta de
    entrada de impersonação.
    """
    s = unicodedata.normalize("NFKD", raw or "").encode("ascii", "ignore").decode().lower().strip()
    s = re.sub(r"[\s_]+", ".", s)
    s = re.sub(r"[^a-z0-9_.-]", "", s)
    s = re.sub(r"[.\-_]{2,}", ".", s).strip("._-")
    return s[:30]


def suggest(conn: Connection, base: str, *, limit: int = 5) -> list[str]:
    """Sugere identificadores livres a partir de um nome. Só devolve o que está realmente disponível."""
    root = normalize(base) or "perfil"
    root = root[:24]
    out: list[str] = []
    for cand in [root] + [f"{root}{n}" for n in range(2, 40)]:
        if len(out) >= limit:
            break
        if HANDLE_RE.match(cand) and available(conn, cand)["available"]:
            out.append(cand)
    return out


def available(conn: Connection, handle: str) -> dict:
    """O identificador está livre? Verifica formato, reserva, uso atual e HISTÓRICO.

    O histórico conta: liberar imediatamente um identificador abandonado permitiria herdar a reputação de quem o usava
    — alguém segue @instituto.agua, o instituto troca, e um terceiro assume o nome antigo.
    """
    h = normalize(handle)
    if not HANDLE_RE.match(h):
        return {"available": False, "handle": h, "reason": "formato inválido",
                "rule": "3 a 30 caracteres: letras, números, ponto, hífen ou sublinhado; começa e termina com "
                        "letra ou número"}
    if conn.one("SELECT 1 AS ok FROM reserved_handles WHERE handle = $1", h):
        return {"available": False, "handle": h, "reason": "identificador reservado pela plataforma"}
    if conn.one("SELECT 1 AS ok FROM public_profiles WHERE handle = $1", h):
        return {"available": False, "handle": h, "reason": "já está em uso"}
    old = conn.one("SELECT at FROM handle_history WHERE handle = $1 ORDER BY at DESC LIMIT 1", h)
    if old:
        return {"available": False, "handle": h,
                "reason": "foi usado por outro perfil e está em período de carência"}
    return {"available": True, "handle": h}


# ------------------------------------------------------------------------------------------------ escrita

def create(conn: Connection, *, handle: str, display_name: str, org_id: str | None = None,
           user_id: str | None = None, headline: str | None = None, bio: str | None = None,
           actor: str | None = None) -> dict:
    if (org_id is None) == (user_id is None):
        raise unprocessable("O perfil é de uma organização OU de uma pessoa")
    chk = available(conn, handle)
    if not chk["available"]:
        raise ApiError(409, "handle_unavailable", f"Identificador indisponível: {chk['reason']}", chk)
    owner_col = "org_id" if org_id else "user_id"
    if conn.one(f"SELECT handle FROM public_profiles WHERE {owner_col} = $1", org_id or user_id):
        raise ApiError(409, "profile_exists", "Este perfil já existe; altere o identificador em vez de criar outro")
    row = conn.one(
        "INSERT INTO public_profiles(org_id, user_id, handle, display_name, headline, bio)"
        " VALUES ($1,$2,$3,$4,$5,$6) RETURNING id::text AS id, handle, created_at",
        org_id, user_id, chk["handle"], display_name, headline, bio)
    rebuild_projection(conn, profile_id=row["id"])
    return {**row, "url": f"/@{row['handle']}"}


def update(conn: Connection, *, profile_id: str, org_id: str | None, user_id: str | None,
           fields: dict[str, Any], actor: str | None = None) -> dict:
    """Edita o perfil. `handle` troca com histórico; `verified_badge` e `suspended` não são editáveis aqui."""
    p = _owned(conn, profile_id, org_id, user_id)
    allowed = {"display_name", "headline", "bio", "visibility", "show_territory", "show_projects",
               "show_credentials", "show_organizations", "show_impact_history", "show_contact", "links"}
    sets, params = [], []
    if "handle" in fields and fields["handle"]:
        chk = available(conn, fields["handle"])
        if chk["handle"] != p["handle"] and not chk["available"]:
            raise ApiError(409, "handle_unavailable", f"Identificador indisponível: {chk['reason']}", chk)
        if chk["handle"] != p["handle"]:
            params.append(chk["handle"])
            sets.append(f"handle = ${len(params) + 1}")
    for k, v in fields.items():
        if k in allowed and v is not None:
            if k == "links":
                v = _clean_links(v)
            params.append(Json(v) if k == "links" else v)
            sets.append(f"{k} = ${len(params) + 1}" + ("::jsonb" if k == "links" else ""))
    if sets:
        conn.run(f"UPDATE public_profiles SET {', '.join(sets)} WHERE id = $1", profile_id, *params)
    return rebuild_projection(conn, profile_id=profile_id)


def _clean_links(links: Any) -> list[dict]:
    """Só http(s), rótulo curto, no máximo 8. Link é a parte do perfil que mais atrai abuso."""
    out = []
    for item in (links or [])[:8]:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not re.match(r"^https?://[^\s<>\"']{4,300}$", url):
            continue
        out.append({"label": str(item.get("label") or url)[:60], "url": url})
    return out


def _owned(conn: Connection, profile_id: str, org_id: str | None, user_id: str | None) -> dict:
    p = conn.one("SELECT id::text AS id, handle, org_id::text AS org_id, user_id::text AS user_id, suspended"
                 " FROM public_profiles WHERE id = $1", profile_id)
    if not p:
        raise not_found("Perfil")
    if p["org_id"] and p["org_id"] != org_id:
        raise forbidden("Perfil de outra organização")
    if p["user_id"] and p["user_id"] != user_id:
        raise forbidden("Perfil de outra pessoa")
    if p["suspended"]:
        raise ApiError(409, "suspended", "Perfil suspenso pela administração")
    return p


# ------------------------------------------------------------------------------------------------ projeção

def rebuild_projection(conn: Connection, *, profile_id: str) -> dict:
    """Monta a projeção pública a partir das tabelas privadas e GRAVA em `public_fields`.

    Esta é a única função do sistema que lê tabela privada com destino público, e por isso é curta, fechada e lida de
    cima a baixo. Tudo o que ela não escreve não existe para o mundo.

    `public_fields` é coluna protegida por `guard_columns`, então a escrita acontece em contexto privilegiado: a
    organização não monta a própria projeção — ela escolhe os interruptores `show_*`, e o servidor monta.
    """
    p = conn.one(
        "SELECT id::text AS id, handle, display_name, headline, bio, org_id::text AS org_id,"
        " user_id::text AS user_id, show_territory, show_projects, show_credentials, show_organizations,"
        " show_impact_history, show_contact, links, visibility, suspended, verified_badge, created_at"
        " FROM public_profiles WHERE id = $1", profile_id)
    if not p:
        raise not_found("Perfil")

    proj: dict[str, Any] = {"handle": str(p["handle"]), "display_name": p["display_name"],
                            "headline": p["headline"], "bio": p["bio"], "links": p["links"],
                            "verified_badge": p["verified_badge"],
                            "member_since": p["created_at"].strftime("%Y-%m") if p["created_at"] else None,
                            "kind": "organization" if p["org_id"] else "person"}

    if p["org_id"]:
        o = conn.one("SELECT coalesce(trade_name, legal_name) AS name, kind, uf, city, mission, founded_on,"
                     " created_at FROM organizations WHERE id = $1", p["org_id"]) or {}
        proj["org_kind"] = o.get("kind")
        proj["mission"] = o.get("mission")
        proj["founded_year"] = o["founded_on"].year if o.get("founded_on") else None
        if p["show_territory"]:
            proj["territory"] = {"uf": o.get("uf"), "city": o.get("city")}
        if p["show_projects"]:
            # SÓ projeto publicado. A condição está aqui e a página pública não repete consulta nenhuma.
            proj["projects"] = conn.query(
                "SELECT title, summary, territory, causes, ods, status, published_at FROM projects"
                " WHERE org_id = $1 AND visibility = 'published' ORDER BY published_at DESC NULLS LAST LIMIT 12",
                p["org_id"])
            proj["projects_count"] = len(proj["projects"])
        if p["show_impact_history"]:
            proj["impact"] = conn.query(
                "SELECT u.period_start, u.period_end, u.summary, u.outcomes, pr.title AS project_title"
                " FROM impact_updates u JOIN projects pr ON pr.id = u.project_id"
                " WHERE u.org_id = $1 AND u.status = 'published' AND pr.visibility = 'published'"
                " ORDER BY u.period_end DESC LIMIT 8", p["org_id"])
        if p["show_contact"]:
            # `contact_email` é o nome real da coluna; só entra quando show_contact está ligado.
            c = conn.one("SELECT contact_email, website FROM organizations WHERE id = $1", p["org_id"]) or {}
            proj["contact"] = {k: v for k, v in c.items() if v}
    else:
        u = conn.one("SELECT created_at FROM users WHERE id = $1", p["user_id"]) or {}
        proj["member_since"] = u["created_at"].strftime("%Y-%m") if u.get("created_at") else proj["member_since"]
        if p["show_credentials"]:
            # Somente credencial VERIFICADA. Credencial declarada não entra: a página pública não repassa afirmação
            # não checada — é o mesmo princípio de Evidence.verified derivar da origem.
            # O registro profissional é (conselho, UF) — número e nome do titular NUNCA entram na projeção:
            # a página pública diz "tem CREA/SP verificado", não qual é o número.
            proj["credentials"] = conn.query(
                "SELECT council, council_code, uf, valid_until FROM professional_credentials"
                " WHERE user_id = $1 AND verification_status = 'verified'"
                "   AND revoked_at IS NULL ORDER BY council LIMIT 12", p["user_id"])
        if p["show_organizations"]:
            proj["organizations"] = conn.query(
                "SELECT coalesce(o.trade_name, o.legal_name) AS name, m.role FROM memberships m"
                " JOIN organizations o ON o.id = m.org_id WHERE m.user_id = $1"
                " ORDER BY coalesce(o.trade_name, o.legal_name) LIMIT 10", p["user_id"])
        if p["show_projects"]:
            # Só experiência CONFIRMADA por quem administra a organização citada (coluna `state`, gatilho
            # experience_confirm_guard). Experiência declarada não entra: a página pública não repassa
            # afirmação sem conferência.
            proj["experiences"] = conn.query(
                "SELECT role, org_name, started_on, ended_on, state FROM professional_experiences"
                " WHERE user_id = $1 AND state = 'confirmed' AND visibility = 'public'"
                " ORDER BY started_on DESC LIMIT 12", p["user_id"])

    # Rede de confiança: só relação de visibilidade pública. O filtro é por `visibility`, nunca por "existe relação".
    subject = ("org", p["org_id"]) if p["org_id"] else ("user", p["user_id"])
    proj["public_relationships"] = conn.query(
        "SELECT r.kind, coalesce(o.trade_name, o.legal_name) AS with_name FROM relationships r"
        " LEFT JOIN organizations o ON o.id = CASE WHEN r.source_org_id = $1 THEN r.target_org_id"
        "                                          ELSE r.source_org_id END"
        " WHERE (r.source_org_id = $1 OR r.target_org_id = $1) AND r.status = 'active'"
        "   AND r.visibility = 'public' AND r.kind <> 'block' ORDER BY r.created_at DESC LIMIT 10",
        subject[1]) if subject[0] == "org" else []

    _assert_no_private(proj)
    conn.run("UPDATE public_profiles SET public_fields = $2::jsonb WHERE id = $1", profile_id, Json(proj))
    return {"id": profile_id, "handle": str(p["handle"]), "url": f"/@{p['handle']}", "fields": sorted(proj.keys())}


def _assert_no_private(proj: dict) -> None:
    """Rede de segurança: nenhum campo proibido entrou na projeção.

    Isto não substitui a lista fechada — é a segunda tranca. Se alguém acrescentar `cnpj` à projeção num refactor
    futuro, o erro acontece na hora de gravar e não em produção, numa página pública.
    """
    flat = _keys(proj)
    bad = sorted(k for k in flat if any(n in k.lower() for n in NEVER_PUBLIC))
    if bad:
        raise AssertionError(f"projeção pública contém campo privado: {', '.join(bad)}")


def _keys(obj: Any, prefix: str = "") -> list[str]:
    if isinstance(obj, dict):
        out = []
        for k, v in obj.items():
            out.append(f"{prefix}{k}")
            out += _keys(v, f"{prefix}{k}.")
        return out
    if isinstance(obj, list):
        out = []
        for item in obj[:3]:
            out += _keys(item, prefix)
        return out
    return []


# ------------------------------------------------------------------------------------------------ leitura pública

def public_page(conn: Connection, handle: str, *, authenticated: bool = False) -> dict:
    """A página pública. LÊ SÓ `public_fields` — nenhuma outra tabela entra nesta consulta.

    A consulta tem uma linha e é intencional: é a frase que um auditor precisa ler para confirmar a regra.
    """
    h = normalize(handle)
    r = conn.one(
        "SELECT id::text AS id, handle, public_fields, visibility, suspended, verified_badge, views, updated_at"
        " FROM public_profiles WHERE handle = $1", h)
    if not r or r["suspended"]:
        # Perfil suspenso responde 404, não 403: dizer "existe mas está suspenso" é informação sobre a moderação.
        raise not_found("Perfil")
    if r["visibility"] == "private":
        raise not_found("Perfil")
    if r["visibility"] == "network" and not authenticated:
        raise ApiError(401, "login_required", "Este perfil é visível apenas para quem tem conta")
    return {"handle": str(r["handle"]), "profile": r["public_fields"], "verified_badge": r["verified_badge"],
            "updated_at": r["updated_at"], "url": f"/@{r['handle']}"}


def open_graph(conn: Connection, handle: str, *, base_url: str) -> dict:
    """Metadados de compartilhamento, montados a partir da MESMA projeção — nunca de tabela privada."""
    page = public_page(conn, handle, authenticated=True)
    f = page["profile"] or {}
    desc = (f.get("headline") or f.get("mission") or f.get("bio") or "Perfil na rede IMPACTO")[:200]
    return {"title": f.get("display_name") or f"@{page['handle']}", "description": desc,
            "url": f"{base_url.rstrip('/')}/@{page['handle']}", "type": "profile",
            "site_name": "IMPACTO", "handle": page["handle"]}


def of_owner(conn: Connection, *, org_id: str | None = None, user_id: str | None = None) -> dict | None:
    col = "org_id" if org_id else "user_id"
    return conn.one(
        f"SELECT id::text AS id, handle, display_name, headline, bio, visibility, suspended, verified_badge,"
        f" show_territory, show_projects, show_credentials, show_organizations, show_impact_history, show_contact,"
        f" links, public_fields, views, updated_at FROM public_profiles WHERE {col} = $1", org_id or user_id)


def handle_timeline(conn: Connection, profile_id: str) -> list[dict]:
    """Histórico de identificadores. Serve a quem precisa provar que o @ mudou e quando."""
    return conn.query("SELECT handle::text AS handle, at, user_display_name(changed_by) AS changed_by"
                      " FROM handle_history WHERE profile_id = $1 ORDER BY at DESC", profile_id)
