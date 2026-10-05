# Release notes — v0.10.0

**Resumo:** adiciona a **camada institucional do terceiro setor**: a plataforma passa a distinguir o que a organização *é* (natureza jurídica), o que *declara* e o que *comprovou* (qualificações e documentos), em que **situação** está e se **pode concorrer a uma oportunidade específica** — sempre com explicação, fonte e o que falta, e sem prometer recurso nem benefício fiscal.

## Para OSCs e coletivos
- Página **Instituição**: natureza jurídica, qualificações (declaradas × verificadas), documentos (AUSENTE · PENDENTE DE VALIDAÇÃO · VALIDADO · EXPIRADO · REJEITADO), maturidade 0–6 e "o que falta".
- Coletivos sem CNPJ podem se cadastrar e participar do que não exige CNPJ.
- Verificar elegibilidade para um edital: 5 estados, com requisito a requisito.
## Para financiadores, empresas e governo
- Critérios institucionais em editais e perfil do financiador; match mostra **bloqueios explicados**.
- Biblioteca de soluções com filtros por natureza jurídica, qualificação verificada, modalidade e prontidão para financiamento.
## Para a administração
- Fila de qualificações e documentos; regras e catálogos com rascunho → revisão → aprovação (por outra pessoa) → publicação.
## O que mudou de comportamento
- Certificação exigida por edital só é aceita se **verificada** pela administração.
## Limites honestos
- Catálogos e regras iniciais são classificação da plataforma, **sem revisão jurídica**; sem integração com bases governamentais; badges não são certificação governamental.

---
# Release notes — v0.9.0 (anterior)

**Resumo:** além do fluxo OSC → edital/fundo → candidatura → execução → prestação de contas (v0.7.0) e dos módulos de impacto, compras, pagamentos registrados, risco, rede, mapa e relatórios (v0.8.0, incluído), esta versão traz a **Biblioteca de Soluções de Impacto**: um banco inteligente de ideias, projetos, metodologias, tecnologias sociais e projetos acadêmicos.

## Biblioteca de Soluções
- **Buscar por intenção**: "artes caps", "projeto idosos", "tenho R$ 250 mil para saúde mental no MT" — o sistema mostra o que entendeu e **por que** cada resultado apareceu.
- **Entender a confiança**: cada solução mostra quem declarou, o que tem evidência, o que foi validado e o que foi apenas autodeclarado. Ideia nunca vira case; "comprovado" só com revisão da administração.
- **Agir**: comparar 2–4 soluções, combinar, "quero algo como este", adaptar para meu território, desenvolver uma ideia (rascunho que exige revisão humana), pedir informações/contato/replicação, declarar interesse de financiamento (identidade privada por padrão), replicar e ter a replicação confirmada pelo autor.
- **Financiadores**: tese de investimento, match explicável e recomendações (personalização só com consentimento).
- **Administração**: fila de verificação, revisão de evidências, validação de resultados, remoção e contestações de autoria.

## Números reais
API 306 operações · 105 tabelas · 207 políticas RLS · 182 testes · busca p95 ≈ 474 ms com 5.000 soluções sintéticas (local).

## Limites (leia)
Sem embeddings (tesauro + FTS + trigramas) · IA opcional e **não usada** na busca/copiloto · pesos de relevância são hipóteses · todos os dados são DEMO · nada foi publicado (web/lojas) · textos legais são minutas [VALIDAR JURÍDICO] · fiscal sem regras aprovadas · pagamentos são registro, sem custódia.

## Atualização
Instale do zero (`ENVIRONMENT_SETUP.md`); migrações 0001–0005 aplicam em sequência. Não há dados legados a migrar. Histórico de versões em `history/`.
