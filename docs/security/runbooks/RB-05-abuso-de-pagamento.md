# RB-05 — Abuso ou fraude em pagamento, doação ou repasse

**Sinais:** casos de risco de doação abertos (`/admin/doacoes/risco`: doação grande, rajada, campanha nova com
entrada grande, fracionamento); sinais de organização (`/admin/risco`: chave PIX repetida entre organizações,
destino de repasse mudado perto do pagamento); estornos/chargebacks em série; evento de webhook rejeitado por
assinatura em quantidade.

**Lembrete:** a plataforma **não guarda dinheiro**. Doações são liquidadas pelo provedor de pagamento; repasses
de acordos são transferências entre as partes. Registro no banco **não é** dinheiro liquidado.

## Conter

1. **Sinal não é acusação.** Abra o caso, atribua a si (`Assumir`), olhe a evidência.
2. Para doação: decida com justificativa (liberar, pedir informação, recusar, comunicar ao provedor). Recusar
   cancela a doação ainda não confirmada. Reter repasse **não existe** nesta versão (depende de contrato com o provedor).
3. Para organização: se há risco real, **proponha** a restrição operacional; **outra pessoa** confirma (v0.35.0).
   A restrição impede publicar, candidatar e aportar — não apaga nada e é reversível.
4. Para repasse em aberto com destino suspeito: avise quem paga para confirmar a chave por telefone antes de transferir.
5. Webhook forjado em série: os eventos sem assinatura válida **não têm efeito** e ficam guardados à parte; se o
   segredo do webhook pode ter vazado → [RB-01](RB-01-vazamento-de-segredo.md).

## Investigar e decidir

- Reúna evidência (referências: doação, evento do provedor, conciliação, documento) no próprio caso.
- A organização pode **recorrer** de decisão que restringiu algo; o recurso é decidido por outra pessoa.
- Suspeita de crime (lavagem, estelionato): decisão do responsável com o jurídico sobre comunicar às autoridades
  e ao provedor. A plataforma não faz essa comunicação sozinha.
