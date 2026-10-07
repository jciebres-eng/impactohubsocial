# EVIDÊNCIA GIT — v0.23.0

> **Ressalva 7 do adendo de auditoria (07/10/2026):** *"O arquivo de projeto recebido não contém
> `.git`; os commits `9ca75f1`, `b4c6958`, `5d0ce11`, `7b286d7`, `67bc6aa` e a tag citados nos
> relatórios permanecem declarações dos documentos anexados, não verificações do histórico Git."*

A ressalva estava certa, e a resposta não é afirmar os commits com mais ênfase. É tornar o histórico
**verificável sem depender da nossa palavra** — por três caminhos independentes.

---

## 1. O histórico está público

```
https://github.com/jciebres-eng/impactohubsocial
branch: audit/v0.23.0-completion
```

**Este documento não fixa o hash do commit, de propósito.** A versão anterior fixava, e ficou errada
no dia seguinte: o relatório final citava cinco commits que uma reescrita de histórico havia
eliminado, e uma auditoria independente encontrou a contradição. Hash escrito em dois lugares vira
contradição no primeiro commit seguinte — e empacotar sempre produz pelo menos mais um commit, porque
o manifesto é escrito depois que o conteúdo fecha.

Os valores vigentes estão em **um** lugar só, gerado **depois** do empacotamento e embarcado no pacote
de auditoria:

```
logs/verificacao_pacote_contra_git.log
```

Esse log traz o commit, o hash da **árvore** e o resultado da conferência arquivo por arquivo. O hash
da árvore é o que mais importa para auditoria: depende só do conteúdo dos arquivos, não de autor,
data ou mensagem. Duas pessoas que reconstruam o mesmo conjunto chegam ao mesmo `tree`.

A tag `v0.23.0-audit-completion` existe **localmente e no bundle**; o envio ao remoto é recusado por
este ambiente (HTTP 403). Quem clonar o GitHub encontra o commit e **não** encontra a tag, e confere
pelo hash do commit ou da árvore. Para publicá-la: `git push --tags` de onde houver permissão.

### Por que os commits citados no relatório anterior não existem mais com aqueles hashes

Os commits `9ca75f1`, `b4c6958`, `5d0ce11`, `7b286d7` e `67bc6aa` **foram reescritos**, e isto precisa
estar escrito onde um auditor vai procurar.

A proteção de push do GitHub recusou a publicação apontando uma chave do Stripe em
`b4c6958:backend/tests/test_v0230_security_gate.py:427`. Ela estava certa: o **controle negativo** da
varredura de segredos escrevia chave da AWS, token do GitHub, chave do Stripe e bloco PEM como
literais, para provar que a varredura os encontra. O HEAD já estava corrigido (as amostras passaram a
ser montadas em pedaços); o **histórico** não.

Havia duas saídas. Uma era clicar no link que o GitHub oferece e **autorizar o segredo** — o oposto
exato do que aquele teste defende, deixando quatro chaves de aparência real no histórico público para
sempre. A outra era reescrever os três commits afetados. Como a branch nunca havia sido publicada,
reescrever não quebra o trabalho de ninguém, e foi o que se fez: `filter-branch` aplicando a mesma
transformação já presente no HEAD, seguido de remoção dos refs de backup, da tag antiga e
`gc --prune=now`.

Resultado conferido: **0 commits alcançáveis contendo o literal**. Os hashes novos estão na tabela
abaixo, e o conteúdo das mensagens é o mesmo.

Vale registrar que **três ferramentas independentes** apontaram para o mesmo arquivo: o
`scripts/secrets_scan.py` deste repositório, o `test_no_secrets_committed` que já existia, e a
proteção de push do GitHub. Nenhuma foi silenciada.

---

## 2. O conteúdo do pacote **é** a árvore do commit — provado arquivo por arquivo

Um ZIP que *afirma* vir de um commit não prova nada sobre esse commit: o manifesto interno confere o
ZIP **contra ele mesmo**, o que detecta corrupção e não detecta divergência entre o que foi empacotado
e o que foi versionado.

`scripts/verify_package_against_git.py` compara o conteúdo do pacote com os **objetos do Git**, pelo
sha1 que o próprio Git calcula (`git hash-object`) — uma cadeia **independente** do sha256 do
manifesto. A saída da execução desta rodada está em `logs/verificacao_pacote_contra_git.log`, no
pacote de auditoria, e termina em:

```
OK: todo arquivo do pacote é o objeto Git do commit, byte a byte.
```

As duas exceções são `RELEASE_MANIFEST.sha256` e `RELEASE_MANIFEST.csv`: o manifesto é escrito
**depois** que o conteúdo está fechado, então não pode coincidir com um objeto do commit. Cada uma tem
o motivo escrito no próprio script.

### A aritmética que o adendo chamou de "diferença compatível"

O adendo observou 1.808 entradas no ZIP contra 1.805 no manifesto de rastreabilidade e tratou a
diferença como compatível. Ela é exatamente **3**, e os três têm nome:

| Arquivo | No manifesto? | Por quê |
|---|---|---|
| `IMPACTO_v0.23.0_TRACEABILITY.json` | não | é o próprio manifesto: não contém o próprio hash |
| `RELEASE_MANIFEST.sha256` | não | é a lista de hashes do pacote, escrita no empacotamento |
| `RELEASE_MANIFEST.csv` | não | idem, em formato tabular |

**1.805 + 3 = 1.808.** As três exceções são as mesmas declaradas em
`test_v0230_release_gate.py::FORA_DO_MANIFESTO`, e um teste reprova se alguém acrescentar uma quarta
sem motivo escrito.

---

## 3. O histórico inteiro, verificável **sem rede**

O pacote de auditoria traz `hashes/impacto-v0.23.0.bundle` — o repositório inteiro num arquivo, com
todos os commits **e a tag** (que o remoto não tem):

```
git bundle verify impacto-v0.23.0.bundle
    → The bundle records a complete history.

git clone impacto-v0.23.0.bundle repo && cd repo
git log --oneline
git rev-parse HEAD^{tree}     # compare com o log de verificação no pacote de auditoria
```

---

## Como um auditor confere tudo isto sem confiar em nós

```bash
# com rede
git clone https://github.com/jciebres-eng/impactohubsocial && cd impactohubsocial
git checkout <commit do log de verificação>

# ou, sem rede, a partir do bundle que acompanha o pacote de auditoria
git clone impacto-v0.23.0.bundle impactohubsocial && cd impactohubsocial

# a árvore tem de bater
git rev-parse HEAD^{tree}        # tem de bater com o log de verificação

# e o pacote tem de ser essa árvore, arquivo por arquivo
unzip IMPACTO_v0.23.0_AUDIT_COMPLETION.zip -d /tmp/pkg
python3 scripts/verify_package_against_git.py /tmp/pkg/plataforma-impacto-v0.23.0
```

Três cadeias independentes precisam concordar: o **sha256** do manifesto (conteúdo do pacote
consigo mesmo), o **sha1** dos objetos Git (pacote contra histórico versionado) e o **remoto
público** (histórico contra terceiro que não somos nós). Divergência em qualquer uma delas aparece.

---

## O que esta evidência NÃO prova

1. **Não prova autoria.** Os commits não são assinados por GPG. Provam que o conteúdo é o que o
   histórico registra, não quem o escreveu.
2. **Não prova que o código faz o que diz.** Isso é o que a suíte de testes e as matrizes endereçam,
   e com os limites declarados em `FINAL_ZERO_PENDING_REPORT.md`.
3. **Não prova o estado do remoto no futuro.** Uma branch publicada pode ser reescrita por quem tem
   permissão. O `tree` citado aqui é o ponto fixo: se ele mudar, não é mais esta entrega.
