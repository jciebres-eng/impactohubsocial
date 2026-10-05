// Central de relatórios (impressão/PDF pelo navegador e CSV) e mapa sem provedor externo.
import { useState } from "react";
import { api, qs } from "../api";
import { Button, Field, PageHead, Panel, Select, StateView, useLoad } from "../ui/kit";
import { Link } from "../router";
import { useSession } from "../session";

function Section({ s }: { s: any }) {
  if (s.kind === "kv") return <dl className="kv">{s.items.map((i: any) => <div key={i.label}><dt>{i.label}</dt><dd>{String(i.value)}</dd></div>)}</dl>;
  if (s.kind === "text") return <p>{s.text}</p>;
  if (s.kind === "table") {
    return s.rows.length === 0 ? <p className="muted">Sem registros.</p> : (
      <div className="table-wrap"><table className="table"><thead><tr>{s.columns.map((c: string) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{s.rows.map((r: any[], i: number) => <tr key={i}>{r.map((c, j) => <td key={j}>{c === null || c === undefined ? "—" : String(c)}</td>)}</tr>)}</tbody></table></div>
    );
  }
  return null;
}

export function ReportCenter() {
  const list = useLoad<any>("/v1/report-center");
  const { me } = useSession();
  const k = me?.active_org?.kind;
  const projects = useLoad<any>(["company", "government", "individual"].includes(k || "") ? "/v1/portfolio" : null);
  const own = useLoad<any>(k === "osc" ? "/v1/projects" : null);
  const [type, setType] = useState("executive");
  const [project, setProject] = useState("");
  const [run, setRun] = useState<string | null>(null);
  const rep = useLoad<any>(run, [run]);
  const options: [string, string][] = [...(own.data?.items || []).map((p: any): [string, string] => [p.id, p.title]), ...((projects.data?.items || []).map((p: any): [string, string] => [p.project_id, p.title]))];
  const path = `/v1/report-center/${type}${qs({ project_id: project })}`;
  return (
    <>
      <PageHead title="Relatórios" sub="Gerados a partir dos dados reais da plataforma. Use “Imprimir / salvar PDF” do navegador." />
      <StateView loading={list.loading} error={list.error} onRetry={list.reload}>
        <div className="stack-lg no-print">
          <Panel title="Gerar relatório">
            <form className="form" onSubmit={(e: any) => { e.preventDefault(); setRun(path); }}>
              <Field label="Tipo"><Select value={type} onChange={setType} options={(list.data?.items || []).map((t: any) => [t.type, t.title])} /></Field>
              <Field label="Projeto"><Select value={project} onChange={setProject} placeholder="Todos" options={options} /></Field>
              <Button type="submit" variant="primary">Gerar</Button>
              <a className="btn btn-ghost" href={path + (path.includes("?") ? "&" : "?") + "format=csv"}>Baixar CSV</a>
            </form>
            {list.data && <p className="muted">{list.data.wording}</p>}
          </Panel>
        </div>
        {run && (
          <StateView loading={rep.loading} error={rep.error} onRetry={rep.reload}>
            {rep.data && (
              <article className="report">
                <header><h2>{rep.data.title}</h2><p className="muted">{rep.data.organization} · {new Date(rep.data.generated_at).toLocaleString("pt-BR")}</p></header>
                {rep.data.sections.map((s: any) => <section key={s.title}><h3>{s.title}</h3><Section s={s} /></section>)}
                <p className="muted">{rep.data.wording}</p>
                <Button variant="ink" className="no-print" onClick={() => window.print()}>Imprimir / salvar PDF</Button>
              </article>
            )}
          </StateView>
        )}
      </StateView>
    </>
  );
}

// Mapa do Brasil em SVG simples (projeção equirretangular), sem tiles externos. Cada ponto já vem com a precisão escolhida pela OSC.
const W = 600, H = 560, LAT = [6, -34], LNG = [-74, -34];
const px = (lng: number) => ((lng - LNG[0]) / (LNG[1] - LNG[0])) * W;
const py = (lat: number) => ((LAT[0] - lat) / (LAT[0] - LAT[1])) * H;

export function MapView() {
  const { data, error, loading, reload } = useLoad<any>("/v1/map/projects");
  return (
    <>
      <PageHead title="Mapa de projetos" sub="Localização aproximada, conforme a precisão escolhida por cada organização." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="grid-home">
            <Panel title="Pontos">
              <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Mapa com ${data.points.length} projetos com localização pública`} className="map">
                <rect width={W} height={H} fill="none" stroke="currentColor" opacity=".25" />
                {data.points.map((p: any) => (
                  <a key={p.id} href={`/projetos/${p.id}`}><circle cx={px(p.lng)} cy={py(p.lat)} r={6} fill="currentColor" opacity=".7"><title>{p.title}</title></circle></a>
                ))}
              </svg>
              {data.points.length === 0 && <p className="muted">Nenhum projeto compartilha ponto no mapa.</p>}
            </Panel>
            <Panel title="Por estado">
              <ul className="rows">{data.by_uf.map((u: any) => <li key={u.uf}><span>{u.uf}</span><span>{u.projects} projeto(s)</span></li>)}</ul>
              <p className="muted">{data.note}</p>
            </Panel>
          </div>
        )}
      </StateView>
    </>
  );
}

export function LocationEditor({ id }: { id: string }) {
  const [precision, setPrecision] = useState("municipality");
  const [lat, setLat] = useState(""); const [lng, setLng] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const need = ["exact", "neighborhood", "approximate"].includes(precision);
  async function save(e: any) {
    e.preventDefault();
    try { await api.put(`/v1/projects/${id}/location`, { precision, lat: lat === "" ? null : Number(lat), lng: lng === "" ? null : Number(lng) }); setMsg("Localização salva."); }
    catch (err: any) { setMsg(err.message); }
  }
  return (
    <>
      <PageHead title="Localização pública" back={<Link to={`/projetos/${id}`} className="back">Projeto</Link>} sub="Defina o quanto da localização aparece para terceiros. Coordenadas exatas ficam só com você, salvo se escolher “exata”." />
      <form className="form" onSubmit={save}>
        <Field label="Precisão"><Select value={precision} onChange={setPrecision} options={[["region", "Somente região"], ["municipality", "Município (sem ponto no mapa)"], ["approximate", "Aproximada (~10 km)"], ["neighborhood", "Bairro (~1 km)"], ["exact", "Exata"]]} /></Field>
        {need && <><Field label="Latitude"><input className="input" type="number" step="any" value={lat} onChange={(e: any) => setLat(e.target.value)} /></Field>
          <Field label="Longitude"><input className="input" type="number" step="any" value={lng} onChange={(e: any) => setLng(e.target.value)} /></Field></>}
        <Button type="submit" variant="primary">Salvar</Button>
        {msg && <p role="status">{msg}</p>}
      </form>
    </>
  );
}
