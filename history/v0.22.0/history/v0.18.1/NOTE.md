# Snapshot da v0.18.1 (linha de base técnica travada)

Documentos como estavam ao fim da v0.18.1, antes da v0.19.0.

**Por que a v0.19.0 existe.** Ao fim da v0.18.1 a pergunta do proprietário foi direta: antes da camada
de design e da publicação, o que ainda falta? A resposta apontou três coisas que, se não fossem feitas
antes, fariam o trabalho de design ser REFEITO, e três que fariam a publicação falhar em silêncio:

1. **Vocabulário.** `config/i18n.json` tinha seis namespaces e nenhum termo da camada de impacto. Os
   rótulos existiam espalhados por doze módulos Python, e uma terceira cópia vivia dentro de uma
   página em TypeScript. Sem consolidar, quem desenha inventaria as palavras e a tela passaria a
   contradizer a API.
2. **Primeiro acesso.** Os 76 estados vazios diziam "Nada aqui" e nada mais: nem por que, nem o que
   fazer, nem o que se ganha.
3. **Retorno por declarar contexto.** A plataforma pedia o dado mais caro do produto e não devolvia
   nada visível para quem preencheu — o sinal existia só do lado de quem financia.
4. **Backup.** O script existia desde a v0.7.0 e NADA o executava.
5. **E-mail.** O cadastro depende do e-mail de verificação, e uma falha de SMTP não deixava registro.
6. **Exclusão (LGPD).** As cascatas da camada nova estavam declaradas nas migrações e nunca haviam
   sido executadas.

O que a v0.19.0 encontrou ao executar essas seis coisas está em `FINAL_PRE_DESIGN_RELEASE_REPORT.md`.
