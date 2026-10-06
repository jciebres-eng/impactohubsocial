# Retrato dos documentos da v0.19.0

Cópia congelada em 06/10/2026, no momento do corte da **v0.20.0**. São 21 arquivos, exatamente
como estavam quando a v0.19.0 foi entregue — nenhum deles foi editado aqui.

## Por que este diretório existe

A regra do projeto é não sobrescrever documento em silêncio. Quando a versão sobe, os documentos
anteriores vêm para cá antes de serem reescritos, para que alguém possa responder depois: *o que a
plataforma afirmava sobre si mesma naquela data?*

## O que estes documentos afirmavam e a v0.20.0 corrigiu

Vale ler com esta lista ao lado, porque algumas afirmações aqui eram **falsas** e a rodada seguinte
as encontrou:

* **`IMPACT_FRAMEWORK_AUDIT.md`** dizia que a v0.18.0 entregava o importador
  `scripts/import_ods_targets.py`. **O arquivo não existia.** A v0.20.0 escreveu o importador e
  corrigiu a frase.
* **`README.md` e `VERSIONING.md`** anunciavam v0.18.1 com o `VERSION` já em 0.19.0.
* **`README.md`, `RELEASE_READINESS.md` e `REQUIREMENTS_MATRIX.md`** diziam "28 motores". O
  registro tinha 28 declarados e o código tinha 40 — doze motores existiam sem estar no
  inventário, incluindo a camada de impacto inteira.
* **Contagem de migrações**: quatro documentos davam quatro números diferentes (32, 32, 34, 36),
  nenhum correto.
* **Contagem de operações**: 749 em um documento, 815 em outro; a real era 837.

Nada disso foi apagado deste retrato. Documento histórico com erro corrigido deixa de ser
histórico — e a correção só é verificável se o erro continuar legível.
