# RB-04 — Perda de arquivos, cifra por terceiro (ransomware) ou bucket apagado

**Sinais:** downloads falham com "não encontrado"; o painel do R2 mostra o bucket vazio ou objetos estranhos;
pedido de resgate; a rotina `pending_scans` acusa muitos arquivos ilegíveis.

## Conter

1. **Troque imediatamente o token do R2 dos arquivos** ([RB-01](RB-01-vazamento-de-segredo.md)) — quem apagou ou
   cifrou tinha esse token (ou a conta Cloudflare).
2. Troque a senha e confira o MFA da **conta Cloudflare**.
3. Acione o interruptor de emergência para envio e download de documentos
   ([RB-06](RB-06-queda-de-provedor-e-interruptor.md)) para ninguém trabalhar sobre arquivos que sumiram.
4. **Não pague resgate.**

## Recuperar

- **Banco**: os registros dos documentos (nome, tipo, hash SHA-256) continuam no banco; o banco tem backup
  próprio ([RB-07](RB-07-perda-do-banco.md)).
- **Arquivos**: nesta versão **não existe cópia dos arquivos do R2** (auditoria, BCP-03 — pendência do
  responsável: ligar versionamento/replicação do bucket). Sem isso, arquivo apagado não volta pela plataforma:
  as organizações precisarão reenviar. O hash guardado no banco permite provar se um arquivo reenviado é o mesmo.
- Avise as organizações afetadas com a lista do que precisa ser reenviado (consulta pelos registros do banco).

## Depois

Ligar versionamento/replicação do bucket e um token separado, só de leitura, para auditoria.
