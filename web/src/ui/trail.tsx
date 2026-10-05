import type { ReactNode } from "react";
import { MATCH_STATE, label } from "../format";
import { Pill } from "./kit";

/** A Trilha: a jornada do recurso, do cadastro à prestação de contas. Elemento de identidade da plataforma. */
export const PLATFORM_TRAIL = [
  ["draft", "Preparação"], ["submitted", "Envio"], ["screening", "Triagem"], ["due_diligence", "Diligência"], ["approved", "Aprovação"],
  ["committed", "Aporte"], ["in_execution", "Execução"], ["reporting", "Prestação de contas"], ["closed", "Encerramento"],
] as const;
export const INTEREST_TRAIL = [["interest", "Interesse"], ...PLATFORM_TRAIL.slice(3)] as const;
export const EXTERNAL_TRAIL = [["draft", "Preparação"], ["submitted", "Protocolo"], ["approved", "Resultado"], ["in_execution", "Execução"],
  ["reporting", "Prestação de contas"], ["closed", "Encerramento"]] as const;

export function Trail({ steps, current, ended }: { steps: readonly (readonly [string, string])[]; current: string; ended?: string }) {
  const idx = steps.findIndex(([k]) => k === current);
  return (
    <div className="trail-wrap">
      <ol className="trail" aria-label="Etapas">
        {steps.map(([k, l], i) => {
          const state = idx < 0 ? "todo" : i < idx ? "done" : i === idx ? "now" : "todo";
          return (
            <li key={k} className={`trail-step trail-${state}`} aria-current={state === "now" ? "step" : undefined}>
              <span className="trail-dot" aria-hidden="true">{state === "done" ? "✓" : i + 1}</span>
              <span className="trail-name">{l}</span>
            </li>
          );
        })}
      </ol>
      {ended && <p className="trail-ended">Encerrada como <strong>{label(ended)}</strong>.</p>}
    </div>
  );
}

const SIGNAL_TONE = ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9"];

/** Veredito explicável do Match: estado, composição do score por critério, requisitos, riscos, lacunas e próxima ação. */
export function MatchVerdict({ m, compact, actions }: { m: any; compact?: boolean; actions?: ReactNode }) {
  if (!m) return null;
  const st = MATCH_STATE[m.recommended_state] || { label: m.recommended_state, tone: "muted" };
  const known = (m.signals || []).filter((s: any) => s.value !== null);
  const totalW = (m.signals || []).reduce((a: number, s: any) => a + s.weight, 0) || 1;
  return (
    <div className={`verdict verdict-${st.tone}`}>
      <div className="verdict-head">
        <div>
          <p className="verdict-state">{st.label}</p>
          <p className="verdict-meta">
            {m.score === null ? "Dados insuficientes para pontuar" : <>Compatibilidade <strong>{Math.round(m.score)}</strong> de 100</>}
            {" · "}confiança dos dados {Math.round(m.confidence)}%
          </p>
        </div>
        {actions}
      </div>
      {!compact && known.length > 0 && (
        <div className="meter" aria-label="Contribuição de cada critério">
          {known.map((s: any, i: number) => (
            <span key={s.key} className={`meter-seg ${SIGNAL_TONE[i % 9]}`} title={`${s.label}: ${Math.round(s.value * 100)}%`}
              style={{ width: `${(s.weight * s.value / totalW) * 100}%` }} />
          ))}
        </div>
      )}
      {m.blockers?.length > 0 && (
        <div className="verdict-block">
          <h3>Impedimentos</h3>
          <ul className="list-bad">{m.blockers.map((b: any) => <li key={b.code}>{b.message}{b.how_to_fix && <span className="how"> — {b.how_to_fix}</span>}</li>)}</ul>
        </div>
      )}
      {!compact && m.requirements?.length > 0 && (
        <div className="verdict-block">
          <h3>Requisitos e pré-requisitos</h3>
          <ul className="reqs">
            {m.requirements.map((r: any) => (
              <li key={r.code} className={`req req-${r.status}`}>
                <span className="req-mark" aria-hidden="true">{r.status === "met" ? "✓" : r.status === "unmet" ? "✕" : "?"}</span>
                <span><strong>{r.label}</strong>{!r.mandatory && <em> (recomendado)</em>}<br /><span className="muted">{r.detail}</span>
                  {r.status !== "met" && r.how_to_fix && <span className="how"> {r.how_to_fix}</span>}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="verdict-grid">
        {m.why_match?.length > 0 && (
          <div><h3>Por que combina</h3><ul>{m.why_match.map((w: any) => <li key={w.key}>{w.label}: {w.detail}</li>)}</ul></div>
        )}
        {m.why_not?.length > 0 && (
          <div><h3>Por que não combina tanto</h3><ul>{m.why_not.map((w: any) => <li key={w.key}>{w.label}: {w.detail}</li>)}</ul></div>
        )}
        {m.risks?.length > 0 && (
          <div><h3>Riscos</h3><ul>{m.risks.map((r: any) => <li key={r.code}><Pill tone={r.severity === "high" ? "bad" : "warn"}>{r.severity === "high" ? "alto" : r.severity === "medium" ? "médio" : "baixo"}</Pill> {r.message}</li>)}</ul></div>
        )}
        {m.missing_data?.length > 0 && (
          <div><h3>Dados ausentes</h3><ul>{m.missing_data.map((d: any) => <li key={d.field}>{d.label}</li>)}</ul></div>
        )}
      </div>
      {m.next_action && <p className="verdict-next"><strong>Próxima ação:</strong> {m.next_action.label}</p>}
      {!compact && <p className="fineprint">{m.disclaimer} Motor {m.engine_version}, pesos {m.weights_version}.</p>}
    </div>
  );
}
