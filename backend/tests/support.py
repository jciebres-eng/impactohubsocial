"""Infraestrutura de testes: PostgreSQL REAL descartável + servidor HTTP REAL (uvicorn) + cliente HTTP.

Variáveis:
  TEST_ADMIN_DATABASE_URL  superusuário para criar/dropar o banco de teste (padrão: postgresql://postgres@127.0.0.1:5432/postgres)
  TEST_KEEP_DB=1           não remove o banco ao final (depuração)
Os papéis impacto_owner/impacto_app são criados pelo bootstrap se não existirem (senhas apenas de teste).
"""
from __future__ import annotations

import atexit
import email
import http.cookiejar
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
os.environ.setdefault("PASSWORD_SCRYPT_N", str(2 ** 14))

ADMIN_URL = os.getenv("TEST_ADMIN_DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/postgres")
_P = urllib.parse.urlparse(ADMIN_URL)
HOST, PORT = _P.hostname or "127.0.0.1", _P.port or 5432
DB_NAME = f"impacto_test_{os.getpid()}"
#: UMA senha por processo para cada papel, usada por TODO teste. `impacto_owner` e `impacto_app` são
#: papéis da INSTÂNCIA, não do banco: um teste que lhes dê senha própria derruba a conexão de todos os
#: que rodam depois. Aqui isso nunca apareceu porque o PostgreSQL local autentica em `trust` (aceita
#: qualquer senha); no CI ele confere a senha, e a primeira execução real da suíte no GitHub (v0.24.0)
#: deu 105 erros "password authentication failed" por causa de três classes que faziam isso.
OWNER_PW, APP_PW = "owner_test_pw_" + uuid.uuid4().hex[:6], "app_test_pw_" + uuid.uuid4().hex[:6]
OWNER_DSN = f"host={HOST} port={PORT} dbname={DB_NAME} user=impacto_owner password={OWNER_PW}"
APP_DSN = f"host={HOST} port={PORT} dbname={DB_NAME} user=impacto_app password={APP_PW}"
TMP = Path(tempfile.mkdtemp(prefix="impacto-test-"))

_state: dict = {}
_lock = threading.Lock()


def _psql(*args: str) -> str:
    return subprocess.run(["psql", ADMIN_URL, "-v", "ON_ERROR_STOP=1", "-q", "-tA", *args], check=True,
                          capture_output=True, text=True).stdout


def _create_db() -> None:
    _psql("-c", f'DROP DATABASE IF EXISTS "{DB_NAME}" WITH (FORCE)')
    subprocess.run(["psql", ADMIN_URL, "-v", "ON_ERROR_STOP=1", "-q", "-v", f"db={DB_NAME}", "-f", str(ROOT / "infra/db/bootstrap.sql")],
                   check=True, capture_output=True, text=True)
    _psql("-c", f"ALTER ROLE impacto_owner PASSWORD '{OWNER_PW}'; ALTER ROLE impacto_app PASSWORD '{APP_PW}';")
    from impacto.db.migrate import migrate
    migrate(OWNER_DSN, log=lambda *_: None)
    _declare_test_prices()


#: A v0.17.0 APOSENTOU a regra comercial em dólar da v0.16.0 e **não** fixou preço institucional: as
#: faixas são hipóteses declaradas, e sem preço a plataforma recusa contratação online. Isso é o
#: comportamento certo do produto, mas deixa a suíte sem nada para exercitar na camada de cobrança.
#:
#: Então o AMBIENTE DE TESTE declara uma regra comercial própria, em BRL, como faria o proprietário ao
#: publicar preço. Os valores abaixo existem só aqui: não estão em `config/plans.json`, não vão para
#: produção, e o `reason` de cada versão diz isso em letras.
#: Marcador do `reason` das versões de preço criadas pelo ambiente. Existe para que um cenário de
#: teste consiga REABRIR exatamente estas — e não qualquer versão fechada do mesmo plano, que é o que
#: produzia violação de `ux_price_current`.
TEST_PRICE_REASON = "Preço declarado pelo AMBIENTE DE TESTE."
TEST_PRICES = (
    # (plano, intervalo, centavos, entrada, períodos de entrada, dias de teste)
    ("osc_premium", "month", 9900, 1900, 3, 14),
    ("osc_premium", "year", 99000, None, None, 14),
    ("provider_premium", "month", 4900, None, None, 14),
    ("company_premium", "month", 29900, None, None, 14),
)


def _declare_test_prices() -> None:
    """Publica a tabela do ambiente de teste POR CIMA da tabela real, pelo caminho legítimo.

    Até a v0.20.0 o catálogo real estava vazio e bastava inserir. A v0.21.0 publicou a Pricing
    Version 2027.01, e aí a inserção direta passou a violar `ux_price_current` — o índice que
    garante UMA versão vigente por (plano, intervalo, moeda). Isso não é um estorvo do teste: é o
    índice fazendo exatamente o trabalho dele.

    Então o ambiente faz o que o proprietário faria para republicar um preço: FECHA a vigência da
    versão atual e abre a sua. O histórico fica, o caminho exercitado é o de produção, e os valores
    de teste continuam existindo só aqui.
    """
    from impacto.db.pq import Connection
    c = Connection(OWNER_DSN)
    try:
        for plan, interval, cents, intro, periods, trial in TEST_PRICES:
            c.run("UPDATE plan_price_versions SET effective_until = now()"
                  " WHERE plan_key = $1 AND interval = $2 AND currency = 'BRL'"
                  " AND effective_until IS NULL", plan, interval)
            # IDEMPOTENTE: se esta mesma versão do ambiente já existe fechada, REABRE em vez de
            # inserir outra. Sem isto, cada chamada empilhava uma versão de teste a mais, e o
            # `tearDownClass` de test_v0110 — que reabre TODAS as fechadas com este `reason` —
            # passava a abrir duas ao mesmo tempo e violava `ux_price_current`.
            #
            # A função é chamada mais de uma vez de propósito: `test_v0170` roda
            # `sync_reference_data`, que reaplica a tabela de produção, e precisa devolver o
            # ambiente como encontrou.
            if c.run("UPDATE plan_price_versions SET effective_until = NULL"
                     " WHERE id = (SELECT id FROM plan_price_versions"
                     "             WHERE plan_key = $1 AND interval = $2 AND currency = 'BRL'"
                     "               AND amount_cents = $3 AND reason LIKE $4"
                     "             ORDER BY effective_from DESC LIMIT 1)",
                     plan, interval, cents, TEST_PRICE_REASON + "%"):
                continue
            c.run("INSERT INTO plan_price_versions(plan_key, interval, currency, amount_cents,"
                  " intro_amount_cents, intro_periods, trial_days, tax_behavior, provider, reason)"
                  " VALUES ($1,$2,'BRL',$3,$4,$5,$6,'exclusive','stripe',$7)",
                  plan, interval, cents, intro, periods, trial,
                  TEST_PRICE_REASON + " A v0.17.0 não fixa preço institucional; este valor existe "
                  "apenas para exercitar a camada de cobrança.")
    finally:
        c.close()


def _drop_db() -> None:
    if os.getenv("TEST_KEEP_DB") == "1":
        return
    try:
        _psql("-c", f'DROP DATABASE IF EXISTS "{DB_NAME}" WITH (FORCE)')
    except Exception:
        pass
    shutil.rmtree(TMP, ignore_errors=True)


def test_env() -> dict:
    return {
        "IMPACTO_ENV": "test", "DATABASE_URL": APP_DSN, "SECRET_KEY": "test-secret-key-" + "x" * 32,
        "VOUCHER_HMAC_KEY": "test-voucher-key-" + "y" * 32, "STORAGE_LOCAL_DIR": str(TMP / "storage"),
        "PUBLIC_BASE_URL": "http://testserver.local", "COOKIE_SECURE": "false", "BILLING_PROVIDER": "sandbox", "TRIAL_AUTO_START": "false",
        "AI_PROVIDER": "local", "MAIL_PROVIDER": "console", "LOG_LEVEL": "WARNING", "ALLOW_UNSCANNED_DOWNLOADS": "true", "RATE_LIMIT_MULTIPLIER": "1000",
    }


def server() -> dict:
    """Sobe (uma vez por processo) banco + servidor. Retorna {'base': url, 'state': AppState}."""
    with _lock:
        if _state:
            return _state
        os.environ.update(test_env())
        _create_db()
        atexit.register(_drop_db)
        import uvicorn
        from impacto.app import AppState, create_app
        from impacto.config import load_settings
        settings = load_settings()
        st = AppState(settings)
        app = create_app(settings, st)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        # `server_header=False` espelha o `--no-server-header` do Dockerfile: o servidor de teste
        # tem de responder como o de produção responde, senão o smoke de publicação mede outra
        # coisa (foi o que aconteceu nesta rodada: o smoke acusou vazamento que só existia aqui).
        cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", lifespan="on",
                             server_header=False)
        srv = uvicorn.Server(cfg)
        t = threading.Thread(target=srv.run, daemon=True)
        t.start()
        for _ in range(100):
            if srv.started:
                break
            time.sleep(0.05)
        _state.update({"base": f"http://127.0.0.1:{port}", "state": st, "server": srv})
        return _state


def owner_conn():
    """Conexão como DONO do banco. Usada só para provar que adulterar a cadeia de custódia exige esse nível de acesso
    (o papel da aplicação não tem UPDATE nessas tabelas e ainda bate no gatilho append-only)."""
    from impacto.db.pq import Connection
    return Connection(OWNER_DSN)


def outbox_messages() -> list[email.message.Message]:
    box = TMP / "outbox"
    if not box.exists():
        return []
    return [email.message_from_bytes(p.read_bytes()) for p in sorted(box.glob("*.eml"))]


def last_signature_code(to: str) -> str:
    """Código de 6 dígitos do e-mail de confirmação de assinatura (segunda camada)."""
    for msg in reversed(outbox_messages()):
        if msg["To"] == to and "assinar" in (msg["Subject"] or "").lower():
            m = re.search(r"\b(\d{6})\b", msg.get_payload(decode=True).decode())
            if m:
                return m.group(1)
    raise AssertionError(f"código de assinatura não encontrado para {to}")


def last_token_for(to: str, path: str) -> str:
    for msg in reversed(outbox_messages()):
        if msg["To"] == to:
            body = msg.get_payload(decode=True).decode()
            m = re.search(re.escape(path) + r"\?token=([A-Za-z0-9_\-]+)", body)
            if m:
                return m.group(1)
    raise AssertionError(f"token {path} não encontrado para {to}")


class Response:
    def __init__(self, status: int, headers, body: bytes):
        self.status, self.headers, self.body = status, headers, body

    @property
    def json(self):
        return json.loads(self.body) if self.body else None

    def __repr__(self):
        return f"<{self.status} {self.body[:300]!r}>"


class Client:
    """Cliente HTTP real. mode='token' (Bearer, como o app mobile) ou 'cookie' (como o navegador, com CSRF)."""

    def __init__(self, mode: str = "token"):
        self.base = server()["base"]
        self.mode = mode
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.access = self.refresh_token = self.csrf = None
        self.user = None

    def request(self, method: str, path: str, body=None, *, headers=None, raw: bytes | None = None, ctype=None) -> Response:
        h = dict(headers or {})
        data = None
        if raw is not None:
            data = raw
            if ctype:
                h["Content-Type"] = ctype
        elif body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        if self.mode == "token":
            h.setdefault("X-Auth-Mode", "token")
            if self.access:
                h.setdefault("Authorization", f"Bearer {self.access}")
        elif self.csrf and method in ("POST", "PUT", "PATCH", "DELETE"):
            h.setdefault("X-CSRF-Token", self.csrf)
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            with self.opener.open(req, timeout=60) as r:
                return Response(r.status, r.headers, r.read())
        except urllib.error.HTTPError as e:
            return Response(e.code, e.headers, e.read())

    def get(self, p, **kw):
        return self.request("GET", p, **kw)

    def post(self, p, body=None, **kw):
        return self.request("POST", p, body if body is not None else {}, **kw)

    def put(self, p, body=None, **kw):
        return self.request("PUT", p, body, **kw)

    def patch(self, p, body=None, **kw):
        return self.request("PATCH", p, body, **kw)

    def delete(self, p, **kw):
        return self.request("DELETE", p, **kw)

    def login(self, email: str, password: str) -> Response:
        r = self.post("/v1/auth/login", {"email": email, "password": password})
        if r.status == 200 and r.json.get("mfa_required") is False:
            self._absorb(r.json)
        return r

    def _absorb(self, data: dict):
        self.access = data.get("access_token") or self.access
        self.refresh_token = data.get("refresh_token") or self.refresh_token
        self.csrf = data.get("csrf_token") or self.csrf

    def upload(self, path: str, filename: str, content: bytes, fields: dict | None = None) -> Response:
        boundary = "----impacto" + uuid.uuid4().hex
        parts = []
        for k, v in (fields or {}).items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                     f"Content-Type: application/octet-stream\r\n\r\n".encode() + content + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        return self.request("POST", path, raw=b"".join(parts), ctype=f"multipart/form-data; boundary={boundary}")


PASSWORD = "Senha-Teste-Forte-2026"
_cnpj_seq = [100000000000]


def next_cnpj() -> str:
    from impacto.services.validators import cnpj_with_check_digits
    _cnpj_seq[0] += 1
    return cnpj_with_check_digits(str(_cnpj_seq[0]))


def new_account(kind: str = "osc", *, verify: bool = True, mode: str = "token", compliance: str | None = None, **org) -> Client:
    """Cadastra usuário + organização via API real, confirma e-mail pelo link do outbox e faz login."""
    c = Client(mode)
    em = f"{kind}-{uuid.uuid4().hex[:10]}@teste.org"
    payload = {"email": em, "password": PASSWORD, "full_name": f"Usuária {kind}", "accept_terms": True,
               "organization": {"kind": kind, "legal_name": org.pop("legal_name", f"Org {kind} {uuid.uuid4().hex[:6]}"),
                                "cnpj": next_cnpj() if kind not in ("provider", "individual") else None, "uf": org.pop("uf", "MT")}}
    r = c.post("/v1/auth/register", payload)
    assert r.status == 202, r
    if verify:
        tok = last_token_for(em, "/verificar-email")
        assert c.post("/v1/auth/verify-email", {"token": tok}).status == 200
    assert c.login(em, PASSWORD).status == 200
    c.email = em
    me = c.get("/v1/me").json
    c.user = me["user"]
    c.org_id = me["active_org"]["id"] if me["active_org"] else None
    if compliance:
        set_compliance(c.org_id, compliance)
    return c


def app_tx(c, *, readonly: bool = False):
    """Conexão no papel da APLICAÇÃO, no contexto desta usuária/organização — sem privilégio.

    Serve para provar que as travas do banco (guard_columns, estado inicial, append-only) valem no caminho real do
    produto. `db_system()` não serve a esse propósito: contexto de sistema é privilegiado por definição, e as travas
    o dispensam de propósito, para que trabalhos internos possam corrigir dados.
    """
    from impacto.db.pool import DbContext
    kind = c.get("/v1/me").json["active_org"]["kind"] if c.org_id else None
    return server()["state"].pool.tx(
        DbContext(user_id=c.user["id"], org_id=c.org_id, org_kind=kind, platform_admin=False), readonly=readonly)


def db_system():
    """Conexão de teste no contexto de sistema (para preparar cenários que exigem a administração)."""
    from impacto.db.pool import DbContext
    return server()["state"].pool.tx(DbContext(system=True))


def set_compliance(org_id: str, status: str) -> None:
    with db_system() as c:
        c.run("UPDATE organizations SET compliance_status = $2 WHERE id = $1", org_id, status)


def set_role(user_id: str, org_id: str, role: str) -> None:
    """Troca o papel da pessoa na organização, pelo banco.

    A rota real exige um segundo membro com papel de dono (uma organização não pode ficar sem
    dono), e o assunto dos testes que usam isto é a CONFERÊNCIA DE PAPEL na rota, não o fluxo de
    gestão de equipe — que tem testes próprios em `test_api_auth.py`.
    """
    with db_system() as c:
        n = c.run("UPDATE memberships SET role = $3 WHERE user_id = $1 AND org_id = $2",
                  user_id, org_id, role)
        assert n == 1, f"nenhum vínculo de {user_id} com {org_id}"


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# CÓDIGO TOTP QUE NÃO SE REPETE
#
# A v0.23.0 fechou o reuso de código TOTP: `verify_once()` grava o contador aceito e o gatilho
# `totp_counter_moves_forward` recusa aceitar um contador igual ou menor. A trava é correta e a
# auditoria a pediu — mas ela quebrou os auxiliares de teste, que gravavam `totp.totp(segredo)`
# duas vezes seguidas (ligar o MFA e depois reautenticar) dentro da mesma janela de 30 segundos.
#
# O defeito encontrou o teste, não o contrário: o arranjo só funcionava porque o reuso era possível.
#
# `fresh_totp()` emite um código por PASSO DISTINTO, sempre à frente do último usado, a partir do
# passo atual (n, n+1). Usar n-1 dava três códigos por janela, mas falhava quando a requisição
# cruzava a virada de 30 s (v0.24.1). Quando os dois códigos da janela acabam, o auxiliar espera a
# próxima. Ainda assim, a resposta certa para quem precisa de muitos códigos seguidos é reaproveitar
# a sessão já reautenticada (a janela de step-up dura 15 minutos).
_ultimo_passo: dict[str, int] = {}


def fresh_totp(secret: str) -> str:
    """Código TOTP ainda não usado para `secret`, válido quando o servidor o conferir.

    Começa no passo ATUAL, não no anterior. A versão anterior começava em `agora - 1` para caber três
    códigos por janela — e falhava quando a requisição cruzava uma virada de 30 s entre gerar e
    conferir: o servidor já estava em `agora + 1`, e a janela de ±1 passo não alcança `agora - 1`.
    Raro por chamada, frequente numa suíte que liga o segundo fator em centenas de contas; foi a
    falha intermitente de `make_staff` que apareceu na primeira execução da suíte com senha exigida.

    Quando os códigos da janela acabam (o servidor queima cada contador usado), espera a próxima em
    vez de falhar: o código seguinte passa a existir, só não existia ainda.
    """
    from impacto.security import totp as _t
    while True:
        agora = int(time.time() // 30)
        passo = max(agora, _ultimo_passo.get(secret, agora - 1) + 1)
        if passo <= agora + 1:
            break
        time.sleep(max(0.0, (agora + 1) * 30 - time.time()) + 0.05)
    _ultimo_passo[secret] = passo
    return _t.totp(secret, at=passo * 30)


def make_admin(mfa: bool = True) -> tuple[Client, str | None]:
    c = new_account("osc")
    with db_system() as db:
        plat = db.scalar("SELECT id::text FROM organizations WHERE kind = 'platform' LIMIT 1") or db.scalar(
            "INSERT INTO organizations(kind, legal_name, compliance_status) VALUES ('platform','Plataforma','approved') RETURNING id::text")
        db.run("UPDATE users SET is_platform_admin = true WHERE id = $1", c.user["id"])
        db.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'owner') ON CONFLICT DO NOTHING", c.user["id"], plat)
    secret = None
    if mfa:
        secret = c.post("/v1/auth/mfa/setup").json["secret"]
        r = c.post("/v1/auth/mfa/enable", {"code": fresh_totp(secret)})
        assert r.status == 200, f"mfa/enable recusou: {r.status} {r.json}"
    assert c.post("/v1/me/switch-org", {"org_id": plat}).status == 200
    # v0.22.0 — ADMINISTRADOR TRABALHANDO. A partir desta versão, as permissões de
    # `core/access.py::STEP_UP_PERMISSIONS` exigem identidade confirmada há menos de 15 minutos:
    # aprovar preço, lançar no financeiro, estornar, conceder papel interno, executar manutenção.
    #
    # Este arranjo representa alguém que acabou de entrar para trabalhar, então ele confirma. Sem
    # isso, catorze testes de domínio passariam a reprovar por um motivo que não é o assunto deles
    # — e a tentação seria tirar a exigência das rotas.
    #
    # A exigência em si é exercitada em `test_v0220_authorization.StepUpTests`, com `make_staff`,
    # que de propósito NÃO confirma: lá o assunto é o step-up.
    if mfa:
        assert c.post("/v1/auth/reauth", {"password": PASSWORD,
                                          "mfa_code": fresh_totp(secret)}).status == 200
        c.mfa_secret = secret
    return c, secret


def grant_premium(c: Client, plan: str | None = None) -> None:
    """Concede plano pago por grant administrativo (como faria um voucher) — evita limites do plano gratuito nos testes."""
    kind = c.get("/v1/me").json["active_org"]["kind"]
    plan = plan or {"osc": "osc_premium", "company": "company_premium", "provider": "provider_premium",
                    "individual": "individual_basic", "government": "gov_institutional"}.get(kind)
    assert plan, f"sem plano conhecido para organização do tipo {kind!r}"
    with db_system() as d:
        d.run("INSERT INTO entitlement_grants(org_id, plan_key, source, ends_at) VALUES ($1,$2,'admin', now() + interval '30 days')", c.org_id, plan)


def make_staff(*roles: str, mfa: bool = True) -> Client:
    """Pessoa da EQUIPE INTERNA com papéis nomeados — e SEM `is_platform_admin`.

    Esta é a diferença que a v0.22.0 trouxe e que `make_admin` não exercita: até então havia um
    booleano só para toda a equipe, e qualquer administrador alcançava receita, custo de IA e
    tabela de preço. `make_staff("support")` cria alguém que atende chamado e NÃO vê dinheiro —
    exatamente o cenário que não era possível representar.

    O MFA é ligado porque toda rota `auth="admin"` o exige na sessão.
    """
    c = new_account("osc")
    with db_system() as db:
        plat = db.scalar("SELECT id::text FROM organizations WHERE kind = 'platform' LIMIT 1") or db.scalar(
            "INSERT INTO organizations(kind, legal_name, compliance_status)"
            " VALUES ('platform','Plataforma','approved') RETURNING id::text")
        db.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'viewer')"
               " ON CONFLICT DO NOTHING", c.user["id"], plat)
        for papel in roles:
            db.run("INSERT INTO staff_roles(user_id, role, granted_by) VALUES ($1,$2,$1)"
                   " ON CONFLICT DO NOTHING", c.user["id"], papel)
    if mfa:
        segredo = c.post("/v1/auth/mfa/setup").json["secret"]
        r = c.post("/v1/auth/mfa/enable", {"code": fresh_totp(segredo)})
        assert r.status == 200, f"mfa/enable recusou: {r.status} {r.json}"
        c.mfa_secret = segredo
    assert c.post("/v1/me/switch-org", {"org_id": plat}).status == 200
    c.staff_roles = tuple(roles)
    return c


def reauth(c: Client) -> None:
    """Confirma a identidade da sessão — exigido pelas permissões de STEP_UP_PERMISSIONS."""
    corpo = {"password": PASSWORD}
    segredo = getattr(c, "mfa_secret", None)
    if segredo:
        corpo["mfa_code"] = fresh_totp(segredo)
    r = c.post("/v1/auth/reauth", corpo)
    assert r.status == 200, r


def make_admin_without_reauth() -> Client:
    """Administrador com MFA e SEM identidade confirmada — para provar que o step-up é real."""
    from impacto.security import totp
    c = new_account("osc")
    with db_system() as db:
        plat = db.scalar("SELECT id::text FROM organizations WHERE kind = 'platform' LIMIT 1") or db.scalar(
            "INSERT INTO organizations(kind, legal_name, compliance_status)"
            " VALUES ('platform','Plataforma','approved') RETURNING id::text")
        db.run("UPDATE users SET is_platform_admin = true WHERE id = $1", c.user["id"])
        db.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'owner')"
               " ON CONFLICT DO NOTHING", c.user["id"], plat)
    segredo = c.post("/v1/auth/mfa/setup").json["secret"]
    assert c.post("/v1/auth/mfa/enable", {"code": totp.totp(segredo)}).status == 200
    c.mfa_secret = segredo
    assert c.post("/v1/me/switch-org", {"org_id": plat}).status == 200
    return c
