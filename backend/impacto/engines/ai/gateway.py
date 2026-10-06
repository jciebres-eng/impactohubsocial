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
from . import local

logger = logging.getLogger("impacto.ai")

_PII = [
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
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
        used = conn.scalar("SELECT count(*) FROM ai_usage WHERE org_id = $1 AND created_at >= date_trunc('month', now())"
                           " AND status <> 'rejected'", ctx.org_id)
        if lim is not None and used >= lim:
            raise ApiError(402, "ai_quota_exceeded", f"Cota mensal de assistência por IA atingida ({lim}). Faça upgrade do plano.",
                           {"limit": lim, "used": used})

    def _log(self, conn, ctx, feature, provider, status, text_in, text_out, meta, latency, redactions):
        usage_id = conn.scalar(
            "INSERT INTO ai_usage(org_id, user_id, feature, provider, model, status, input_chars, output_chars, tokens_in,"
            " tokens_out, latency_ms, input_sha256, redactions) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)"
            " RETURNING id",
            ctx.org_id, ctx.user_id, feature, provider, self.settings.ai_model or None, status, len(text_in), len(text_out),
            meta.get("tokens_in"), meta.get("tokens_out"), int(latency * 1000),
            hashlib.sha256(text_in.encode()).hexdigest(), redactions)
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

    def _external(self, system: str, user: str) -> tuple[str | None, dict, str, int]:
        if not self.external:
            return None, {}, "local", 0
        red, n = redact(user[: self.settings.ai_max_input_chars])
        try:
            text, meta = self.external.complete(SYSTEM_BASE + "\n" + system, red)
            return text, meta, self.provider_name, n
        except Exception as exc:  # noqa: BLE001 — fallback controlado
            log(logger, logging.WARNING, "ai_provider_failed_fallback_local", error_type=type(exc).__name__)
            return None, {"fallback": True}, "local-fallback", n

    # -- recursos ---------------------------------------------------------------------------------
    def structure_need(self, ctx, text: str) -> dict:
        if self.provider_name == "disabled":
            from ...http import ApiError
            raise ApiError(503, "ai_disabled", "Assistência de IA desativada nesta instalação")
        t0 = time.perf_counter()
        with ctx.tx() as c:
            self._check_quota(c, ctx)
            base = local.structure_need(text)
            out_text, meta, provider, n = self._external(
                "Transforme a necessidade descrita em JSON com as chaves: title (<=90 caracteres), summary (<=600), problem, objectives, "
                "beneficiaries_description, questions (lista de perguntas para completar lacunas). Responda SOMENTE com JSON.", text)
            result = dict(base)
            if out_text:
                try:
                    data = json.loads(out_text[out_text.find("{"): out_text.rfind("}") + 1])
                    for k in ("title", "summary", "problem", "objectives", "beneficiaries_description"):
                        if isinstance(data.get(k), str):
                            result[k] = data[k][:2000]
                    if isinstance(data.get("questions"), list):
                        result["questions"] = [str(q)[:300] for q in data["questions"][:8]]
                    result["engine"] = f"{provider}+local-rules"
                except (ValueError, TypeError):
                    result["engine"] = "local-rules@1.0 (resposta externa inválida descartada)"
            self._log(c, ctx, "structure_need", provider, "ok", text, json.dumps(result, ensure_ascii=False), meta,
                      time.perf_counter() - t0, n)
        result.update({"draft": True, "human_review_required": True})
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
            out, meta, provider, n = self._external(
                "Reescreva o rascunho abaixo melhorando clareza e coesão, mantendo TODOS os números, nomes e marcações [COMPLETAR] "
                "exatamente como estão. Não acrescente dados novos. Devolva apenas o texto final.", template)
            content = out.strip() if out and len(out) > 200 else template
            self._log(c, ctx, f"draft:{kind}", provider, "ok", template, content, meta, time.perf_counter() - t0, n)
        return {"content": content, "engine": provider if out else "local-template@1.0", "draft": True, "human_review_required": True}

    def summarize(self, ctx, project: dict) -> dict:
        t0 = time.perf_counter()
        base = local.summarize_project(project)
        with ctx.tx() as c:
            self._check_quota(c, ctx)
            src = "\n".join(str(project.get(k) or "") for k in ("title", "summary", "problem", "objectives", "methodology"))
            out, meta, provider, n = self._external("Resuma em até 4 frases para um financiador, sem adjetivos promocionais.", src)
            text = out.strip()[:1200] if out else base
            self._log(c, ctx, "summarize", provider, "ok", src, text, meta, time.perf_counter() - t0, n)
        return {"summary": text, "engine": provider if out else "local-extractive@1.0", "draft": True}
