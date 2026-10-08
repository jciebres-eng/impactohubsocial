// Build de produção da SPA/PWA com esbuild: bundle com hash, CSS, assets públicos, index.html e service worker versionado.
// Uso: node build.mjs [--watch]   →  saída em web/dist (servida pelo backend em produção)
import { build, context } from "esbuild";
import { createHash } from "node:crypto";
import { cpSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const watch = process.argv.includes("--watch");
const dist = "dist";
rmSync(dist, { recursive: true, force: true });
mkdirSync(join(dist, "assets"), { recursive: true });

const opts = {
  entryPoints: { app: "src/main.tsx", styles: "src/styles.css" },
  bundle: true, minify: !watch, sourcemap: watch ? "inline" : false, format: "esm", target: ["es2020", "chrome90", "firefox90", "safari15"],
  jsx: "automatic", outdir: join(dist, "assets"), entryNames: "[name]-[hash]", metafile: true, legalComments: "eof",
  external: ["/fonts/*"], loader: { ".ttf": "file", ".woff": "file", ".svg": "text" },  // .svg: ícones da identidade entram inline (currentColor)
  define: { "process.env.NODE_ENV": watch ? '"development"' : '"production"', "process.env.IMPACTO_API_BASE": JSON.stringify(process.env.IMPACTO_API_BASE || "") },
  logLevel: "info",
};

function finish(meta) {
  const outs = Object.keys(meta.outputs).map((p) => p.replace(dist + "/", ""));
  const js = outs.find((o) => /^assets\/app-.*\.js$/.test(o));
  const css = outs.find((o) => /^assets\/styles-.*\.css$/.test(o));
  cpSync("public", dist, { recursive: true });
  const html = readFileSync("index.html", "utf8").replace("%CSS%", "/" + css).replace("%JS%", "/" + js);
  writeFileSync(join(dist, "index.html"), html);
  // Lista de pré-cache do service worker (somente shell estático; a API /v1 NUNCA é cacheada).
  const files = [];
  const walk = (d) => readdirSync(d).forEach((f) => { const p = join(d, f); statSync(p).isDirectory() ? walk(p) : files.push(p); });
  walk(dist);
  const precache = files.map((f) => "/" + f.slice(dist.length + 1)).filter((f) => !f.endsWith(".map") && f !== "/sw.js" && !f.endsWith("OFL-1.1.txt"));
  const version = createHash("sha256").update(precache.join("|") + readFileSync(join(dist, js))).digest("hex").slice(0, 12);
  const sw = readFileSync("sw.template.js", "utf8").replace("__VERSION__", version).replace("__PRECACHE__", JSON.stringify(precache.map((p) => (p === "/index.html" ? "/" : p))));
  writeFileSync(join(dist, "sw.js"), sw);
  writeFileSync(join(dist, "build-info.json"), JSON.stringify({ version, built_at: new Date().toISOString(), js, css }, null, 1));
  console.log(`build ok: ${js} ${css} · sw ${version} · ${precache.length} arquivos no pré-cache`);
}

if (watch) {
  const ctx = await context({ ...opts, plugins: [{ name: "finish", setup(b) { b.onEnd((r) => r.metafile && finish(r.metafile)); } }] });
  await ctx.watch();
} else {
  const r = await build(opts);
  finish(r.metafile);
}
