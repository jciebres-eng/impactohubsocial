// Áreas com rolagem alcançáveis pelo teclado (WCAG 2.1.1) — v0.25.0.
//
// O axe-core, rodado pela primeira vez nas 218 telas (job `pilha-do-zero`), acusou
// `scrollable-region-focusable` em /area e /ajuda/comece-aqui: tabela ou bloco de texto que rola na
// horizontal, sem nada focável dentro, não pode ser rolado por quem usa só o teclado. A correção
// padrão é tornar a ÁREA focável — mas só quando ela realmente rola; uma parada de Tab em toda tabela
// que cabe na tela seria ruído para quem navega por teclado. Por isso a decisão é feita na página,
// com o tamanho real, e refeita quando o conteúdo ou a janela mudam.
const ALVOS = "table, .table, .table-wrap, .tabs, .trail-wrap, pre, .modal-body";
const FOCAVEL = "a[href], button, input, select, textarea, [tabindex]:not([tabindex='-1'])";
const MARCA = "data-rolagem-focavel";

function ajustar() {
  for (const el of Array.from(document.querySelectorAll<HTMLElement>(ALVOS))) {
    const estilo = getComputedStyle(el);
    const rolaX = /(auto|scroll)/.test(estilo.overflowX) && el.scrollWidth > el.clientWidth + 1;
    const rolaY = /(auto|scroll)/.test(estilo.overflowY) && el.scrollHeight > el.clientHeight + 1;
    const temFocavel = !!el.querySelector(FOCAVEL);
    const nosso = el.hasAttribute(MARCA);
    if ((rolaX || rolaY) && !temFocavel) {
      if (!el.hasAttribute("tabindex")) {
        el.setAttribute("tabindex", "0");
        el.setAttribute(MARCA, "");
        if (!el.getAttribute("aria-label") && !el.getAttribute("role") && el.tagName !== "TABLE") {
          el.setAttribute("role", "region");
          el.setAttribute("aria-label", "Conteúdo com rolagem");
        }
      }
    } else if (nosso) {
      el.removeAttribute("tabindex");
      el.removeAttribute(MARCA);
      if (el.getAttribute("aria-label") === "Conteúdo com rolagem") {
        el.removeAttribute("aria-label");
        el.removeAttribute("role");
      }
    }
  }
}

export function installScrollFocus() {
  let agendado = 0;
  const agendar = () => {
    if (agendado) return;
    agendado = window.setTimeout(() => { agendado = 0; ajustar(); }, 120);
  };
  new MutationObserver(agendar).observe(document.body, { childList: true, subtree: true });
  window.addEventListener("resize", agendar);
  agendar();
}
