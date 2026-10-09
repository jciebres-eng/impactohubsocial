"""Gateway de IA provider-agnostic.

Controles: cota mensal por organização (plano), redação de dados pessoais antes de envio externo, limite de
contexto, timeout + retries (HttpClient), fallback para o provedor local, log de uso SEM conteúdo (só hash e
tamanhos). A IA nunca decide elegibilidade, aprova, assina ou envia — tudo volta como rascunho para revisão humana.

Provedores: ``local`` (padrão, offline), ``anthropic`` (Messages API), ``openai_compatible`` (/v1/chat/completions),
``disabled``. Modelo e chave vêm de AI_MODEL / AI_API_KEY; nada é codificado.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time

from ...adapters.http_client import HttpClient
from ...observability import METRICS, log
from . import local, policy, prompts
from . import usage_control as UC

logger = logging.getLogger("impacto.ai")

_PII = [
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
    # v0.23.0 — CNPJ faltava. É o identificador que aparece em TODO documento desta plataforma:
    # contrato, nota, estatuto, certidão. Redigir CPF e deixar CNPJ passar protege a pessoa física
    # e entrega a organização, que também é titular de dado protegido por contrato.
    (re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"), "[CNPJ]"),
    # Chave PIX aleatória e número de cartão: não são dado pessoal no sentido estrito, e sair da
    # instalação dentro de um prompt é pior que isso.
    (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[NUMERO_LONGO]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}\b"), "[TELEFONE]"),
    (re.compile(r"\b\d{5}-?\d{3}\b"), "[CEP]"),
    (re.compile(r"\b(?:RG|rg)[:\s]*[\d.\-xX]{5,14}\b"), "[RG]"),
]


def redact(text: str) -> tuple[str, int]:
    n = 0
    for rx, repl in _PII:
        text, k = rx.subn(repl, text)
        n += k
    return text, n


class ExternalLLM:
    def __init__(self, kind: str, base_url: str, api_key: str, model: str, timeout: int, http: HttpClient | None = None):
        self.kind, self.api_key, self.model, self.timeout = kind, api_key, model, timeout
        self.base = (base_url or ("https://api.anthropic.com" if kind == "anthropic" else "")).rstrip("/")
        self.http = http or HttpClient(retries=2)

    def complete(self, system: str, user: str, max_tokens: int = 1500) -> tuple[str, dict]:
        if self.kind == "anthropic":
            status, _, raw = self.http.request("POST", f"{self.base}/v1/messages", timeout=self.timeout, headers={
                "x-api-key": self.api_key, "anthropic-version": "2023-06-01"}, json_body={
                "model": self.model, "max_tokens": max_tokens, "system": system, "temperature": 0.2,
                "messages": [{"role": "user", "content": user}]})
            if status != 200:
                raise RuntimeError(f"provedor de IA retornou {status}")
            data = json.loads(raw)
            text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            usage = data.get("usage", {})
            return text, {"tokens_in": usage.get("input_tokens"), "tokens_out": usage.get("output_tokens")}
        status, _, raw = self.http.request("POST", f"{self.base}/v1/chat/completions", timeout=self.timeout, headers={
            "Authorization": f"Bearer {self.api_key}"}, json_body={
            "model": self.model, "max_tokens": max_tokens, "temperature": 0.2,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        if status != 200:
            raise RuntimeError(f"provedor de IA retornou {status}")
        data = json.loads(raw)
        usage = data.get("usage", {})
        return data["choices"][0]["message"]["content"], {"tokens_in": usage.get("prompt_tokens"), "tokens_out": usage.get("completion_tokens")}


SYSTEM_BASE = ("Você é um assistente de elaboração de projetos sociais no Brasil. Escreva em português do Brasil, de forma clara e "
               "institucional. NUNCA invente números, fontes, leis, metas ou fatos: quando faltar informação, escreva "
               "[COMPLETAR: descrição]. Não faça promessas de resultado nem de benefício fiscal. O texto é um rascunho para revisão humana "
               "e validação por profissional habilitado.")


class AiGateway:
    def __init__(self, settings, http: HttpClient | None = None):
        self.settings = settings
        self.provider_name = settings.ai_provider
        self.external = None
        if settings.ai_provider in ("anthropic", "openai_compatible"):
            self.external = ExternalLLM(settings.ai_provider, settings.ai_base_url, settings.ai_api_key, settings.ai_model,
                                        settings.ai_timeout_seconds, http)

    # -- controle de cota e registro de uso -----------------------------------------------------
    def _check_quota(self, conn, ctx) -> None:
        from ...services.entitlements import effective
        from ...http import ApiError
        ent = effective(conn, ctx.org_id, ctx.principal.org_kind)
        if "*" in ent["features"]:
            return
        lim = ent["limits"].get("ai_requests_month", 0)
        # UMA contagem. Até a v0.20.0 esta consulta e a de `GET /v1/ai/usage` eram cópias que
        # divergiam: aquela não excluía `rejected`, então o painel podia mostrar consumo maior do
        # que o que de fato bloqueava, e a pessoa planejava o mês com o número errado.
        used = conn.scalar("SELECT ai_usage_this_month($1)", ctx.org_id)
        if lim is not None and used >= lim:
            raise ApiError(402, "ai_quota_exceeded", f"Limite mensal de chamadas do pacote de capacidades atingido ({lim}).",
                           {"limit": lim, "used": used})

    def _log(self, conn, ctx, feature, provider, status, text_in, text_out, meta, latency, redactions,
             *, prompt: dict | None = None, schema_valid: bool | None = None,
             credits: int | None = None, idempotency: str | None = None):
        usage_id = conn.scalar(
            "INSERT INTO ai_usage(org_id, user_id, feature, provider, model, status, input_chars, output_chars, tokens_in,"
            " tokens_out, latency_ms, input_sha256, redactions, prompt_key, prompt_version, tier,"
            " schema_valid, credits_charged, idempotency_key, request_id)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)"
            " RETURNING id",
            ctx.org_id, ctx.user_id, feature, provider, self.settings.ai_model or None, status, len(text_in), len(text_out),
            meta.get("tokens_in"), meta.get("tokens_out"), int(latency * 1000),
            hashlib.sha256(text_in.encode()).hexdigest(), redactions,
            (prompt or {}).get("prompt_key"), (prompt or {}).get("version"), (prompt or {}).get("tier"),
            schema_valid, credits, idempotency, getattr(ctx, "request_id", None))
        METRICS.inc("impacto_ai_requests_total", feature=feature, provider=provider, status=status)
        # CUSTO: a auditoria econômica encontrou `ai_usage` registrando tokens e não registrando custo —
        # e sem custo não existe margem por evento de valor, que é o cálculo central desta rodada.
        #
        # O custo é DERIVADO pela função do banco a partir da tabela de preço vigente do provedor. A
        # tabela nasce VAZIA, de propósito: nenhum preço foi inventado no pacote. Sem linha vigente, a
        # chamada fica com `cost_status = 'no_price_table'` e custo nulo — nunca zero, porque zero
        # pareceria custo apurado.
        if usage_id:
            # SAVEPOINT: erro aqui deixaria a transação abortada e o próprio registro de uso seria
            # perdido no COMMIT — foi o que aconteceu na primeira versão desta ligação.
            conn.run("SAVEPOINT ai_cost")
            try:
                conn.scalar("SELECT app_price_ai_usage($1)", int(usage_id))
            except Exception:  # noqa: BLE001 — precificar é instrumentação; não derruba a resposta ao usuário
                conn.run("ROLLBACK TO SAVEPOINT ai_cost")
                log(logger, logging.WARNING, "ai_cost_pricing_failed", usage_id=usage_id)
            else:
                conn.run("RELEASE SAVEPOINT ai_cost")
            if ctx.org_id and status == "ok":
                from ...economics import value_ledger
                # `subject_id` é uuid no ledger e `ai_usage.id` é bigint: o identificador vai em
                # `metrics`, não no campo tipado. (A primeira versão passava um aqui e a gravação era
                # revertida em silêncio pelo savepoint — por isso `record()` agora avisa no log.)
                value_ledger.record(conn, event_type="ai.analysis_completed", org_id=ctx.org_id,
                                    units=1, subject_type="ai_usage",
                                    engine_version=f"{provider}:{self.settings.ai_model or 'local'}",
                                    metrics={"feature": feature, "ai_usage_id": usage_id,
                                             "tokens_in": meta.get("tokens_in"),
                                             "tokens_out": meta.get("tokens_out")})
        return usage_id

    @staticmethod
    def _settle(run: UC.Run, r: dict, prompt: dict, usage_id, text_in: str) -> dict:
        """Liquida a execução na camada de uso: sucesso cobra; provedor externo que falhou ou respondeu
        inválido (resultado veio do motor local de contingência) é PARCIAL e não cobra."""
        partial = r["status"] in ("fallback_local", "invalid_output", "blocked_policy")
        ex = run.ok(result_type="ai_usage", result_id=str(usage_id) if usage_id else None,
                    meta={"tokens_in": r["meta"].get("tokens_in"), "tokens_out": r["meta"].get("tokens_out"),
                          "provider": r["provider"], "prompt_version": f'{prompt["prompt_key"]}@{prompt["version"]}'},
                    partial=partial)
        if usage_id and ex.get("charged_credits"):
            run.conn.run("UPDATE ai_usage SET credits_charged = $2 WHERE id = $1", int(usage_id), int(ex["charged_credits"]))
        return {k: ex.get(k) for k in ("id", "state", "funding_source", "funding_label", "charged_credits", "estimated_credits", "cost_status")}

    def _external(self, conn, prompt: dict, user: str) -> dict:
        """Uma passagem única: política da faixa → redação → chamada → conferência de esquema.

        Devolve um dicionário com `text`, `meta`, `provider`, `redactions`, `status`,
        `schema_valid` e `problems`. O `status` é REAL — antes desta versão o gateway gravava
        sempre `'ok'`, inclusive quando a resposta externa era descartada por ser inválida, e a
        tabela de uso dizia que o provedor externo havia funcionado.
        """
        base = prompts.active(conn, "system_base")
        sistema = prompts.system_text(base) + "\n" + prompt["system_text"]
        conteudo = prompts.wrap_user_content(user)

        politica = policy.load(conn, prompt["tier"])
        tem_externo = bool(self.external)
        try:
            policy.check_request(politica, input_chars=len(conteudo), external=tem_externo)
        except policy.PolicyViolation as pv:
            return {"text": None, "meta": {"policy": pv.code}, "provider": "local",
                    "redactions": 0, "status": "blocked_policy", "schema_valid": None,
                    "problems": [pv.message], "violation": pv}

        if not tem_externo:
            return {"text": None, "meta": {}, "provider": "local", "redactions": 0,
                    "status": "local_only", "schema_valid": None, "problems": []}

        red, n = redact(conteudo)
        try:
            texto, meta = self.external.complete(sistema, red,
                                                 max_tokens=politica["max_output_tokens"])
        except Exception as exc:  # noqa: BLE001 — fallback controlado para o motor local
            log(logger, logging.WARNING, "ai_provider_failed_fallback_local",
                error_type=type(exc).__name__)
            return {"text": None, "meta": {"fallback": True}, "provider": "local-fallback",
                    "redactions": n, "status": "fallback_local", "schema_valid": None,
                    "problems": [f"{type(exc).__name__}"]}

        esquema = prompt.get("output_schema")
        if esquema is None:
            return {"text": texto, "meta": meta, "provider": self.provider_name,
                    "redactions": n, "status": "ok", "schema_valid": None, "problems": []}

        valor, falha = policy.extract_json(texto or "")
        problemas = [falha] if falha else policy.validate(esquema, valor)
        if problemas:
            log(logger, logging.WARNING, "ai_output_rejected_by_schema",
                prompt_key=prompt["prompt_key"], version=prompt["version"],
                problems=problemas[:3])
            return {"text": None, "meta": meta, "provider": self.provider_name,
                    "redactions": n, "status": "invalid_output", "schema_valid": False,
                    "problems": problemas, "value": None}
        return {"text": texto, "meta": meta, "provider": self.provider_name, "redactions": n,
                "status": "ok", "schema_valid": True, "problems": [], "value": valor}

    # -- recursos ---------------------------------------------------------------------------------
    def structure_need(self, ctx, text: str) -> dict:
        if self.provider_name == "disabled":
            from ...http import ApiError
            raise ApiError(503, "ai_disabled", "Assistência de IA desativada nesta instalação")
        t0 = time.perf_counter()
        with ctx.tx() as c:
            self._check_quota(c, ctx)
            self._check_budget(c, ctx)
            prompt = prompts.active(c, "structure_need")
            with UC.Run(c, ctx, "assist.structure_need", params={"sha": hashlib.sha256(text.encode()).hexdigest()},
                        input_chars=len(text)) as run:
                base = local.structure_need(text)
                r = self._external(c, prompt, text)
                result = dict(base)
                if r["status"] == "ok" and r.get("value"):
                    data = r["value"]
                    for k in ("title", "summary", "problem", "objectives", "beneficiaries_description"):
                        if isinstance(data.get(k), str):
                            result[k] = data[k][:2000]
                    if isinstance(data.get("questions"), list):
                        result["questions"] = [str(q)[:300] for q in data["questions"][:8]]
                    result["engine"] = f'{r["provider"]}+local-rules'
                else:
                    # A resposta externa não foi usada, e o resultado diz POR QUÊ. Antes desta versão o
                    # motivo aparecia só como sufixo numa string de motor, e `status` ia como 'ok'.
                    result["engine"] = "local-rules@1.0"
                    result["external_outcome"] = r["status"]
                    if r["problems"]:
                        result["external_problems"] = r["problems"][:3]
                usage_id = self._log(c, ctx, "structure_need", r["provider"], r["status"], text,
                                     json.dumps(result, ensure_ascii=False), r["meta"],
                                     time.perf_counter() - t0, r["redactions"],
                                     prompt=prompt, schema_valid=r["schema_valid"])
                execution = self._settle(run, r, prompt, usage_id, text)
        result.update({"draft": True, "human_review_required": True,
                       "prompt_version": f'{prompt["prompt_key"]}@{prompt["version"]}',
                       "tier": prompt["tier"], "tier_label": prompt["tier_label"], "execution": execution})
        return result

    def draft(self, ctx, kind: str, project: dict, org: dict, call: dict | None, items: list, milestones: list,
              instructions: str | None) -> dict:
        if self.provider_name == "disabled":
            from ...http import ApiError
            raise ApiError(503, "ai_disabled", "Assistência de IA desativada nesta instalação")
        t0 = time.perf_counter()
        template = local.draft_document(kind, project, org, call, items, milestones, instructions)
        with ctx.tx() as c:
            self._check_quota(c, ctx)
            self._check_budget(c, ctx)
            prompt = prompts.active(c, "draft_document")
            with UC.Run(c, ctx, "assist.draft_document", params={"kind": kind, "project": str(project.get("id")), "sha": hashlib.sha256(template.encode()).hexdigest()},
                        input_chars=len(template), project_id=str(project.get("id")) if project.get("id") else None) as run:
                r = self._external(c, prompt, template)
                usou = bool(r["text"]) and len(r["text"]) > 200
                content = r["text"].strip() if usou else template
                if not usou and r["status"] == "ok":
                    r = dict(r, status="invalid_output")
                usage_id = self._log(c, ctx, f"draft:{kind}", r["provider"], r["status"],
                                     template, content, r["meta"], time.perf_counter() - t0, r["redactions"],
                                     prompt=prompt, schema_valid=r["schema_valid"])
                execution = self._settle(run, r, prompt, usage_id, template)
        return {"content": content,
                "engine": r["provider"] if usou else "local-template@1.0",
                "external_outcome": r["status"],
                "prompt_version": f'{prompt["prompt_key"]}@{prompt["version"]}',
                "tier": prompt["tier"], "tier_label": prompt["tier_label"],
                "draft": True, "human_review_required": True, "execution": execution}

    def summarize(self, ctx, project: dict) -> dict:
        t0 = time.perf_counter()
        base = local.summarize_project(project)
        with ctx.tx() as c:
            self._check_quota(c, ctx)
            self._check_budget(c, ctx)
            prompt = prompts.active(c, "summarize_project")
            src = "\n".join(str(project.get(k) or "") for k in ("title", "summary", "problem", "objectives", "methodology"))
            with UC.Run(c, ctx, "assist.summarize_project", params={"sha": hashlib.sha256(src.encode()).hexdigest()},
                        input_chars=len(src), project_id=str(project.get("id")) if project.get("id") else None) as run:
                r = self._external(c, prompt, src)
                text = r["text"].strip()[:1200] if r["text"] else base
                usage_id = self._log(c, ctx, "summarize", r["provider"], r["status"], src, text, r["meta"],
                                     time.perf_counter() - t0, r["redactions"],
                                     prompt=prompt, schema_valid=r["schema_valid"])
                execution = self._settle(run, r, prompt, usage_id, src)
        return {"summary": text,
                "engine": r["provider"] if r["text"] else "local-extractive@1.0",
                "external_outcome": r["status"],
                "prompt_version": f'{prompt["prompt_key"]}@{prompt["version"]}',
                "tier": prompt["tier"], "tier_label": prompt["tier_label"], "draft": True, "execution": execution}

    # -- orçamento em dinheiro --------------------------------------------------------------------
    def _check_budget(self, conn, ctx) -> None:
        """Cota conta CHAMADAS; orçamento limita DINHEIRO. São controles diferentes.

        Uma chamada de 200 mil caracteres consome o mesmo da cota que uma de 200 e custa muito
        mais. `hard_stop` separa "avise" de "pare": um limite que só avisa não é limite, e parar
        sem a organização ter pedido para parar interromperia trabalho por decisão da plataforma.
        """
        from ...http import ApiError
        if not ctx.org_id:
            return
        estado = conn.one("SELECT * FROM ai_budget_state($1, current_date)", ctx.org_id)
        if not estado or estado["state"] != "exceeded" or not estado["hard_stop"]:
            return
        raise ApiError(
            402, "ai_budget_exceeded",
            "O orçamento de IA desta organização para o mês foi atingido e está configurado para "
            "PARAR ao atingir o limite. Ajuste o limite em Configurações → IA para continuar.",
            {"limit_cents": estado["limit_cents"], "spent_cents": estado["spent_cents"],
             "unpriced_calls": estado["unpriced_calls"],
             "note": "Chamadas sem preço vigente na tabela do provedor NÃO entram no gasto "
                     "apurado; `unpriced_calls` diz quantas são."})
