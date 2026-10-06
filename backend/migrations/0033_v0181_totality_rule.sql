-- 0033_v0181_totality_rule.sql — A DOZENA REGRA: AFIRMAÇÃO DE TOTALIDADE EXIGE COBERTURA
--
-- ACHADO DA JORNADA DE PONTA A PONTA (v0.18.1)
--
-- A jornada declarou, de propósito, uma alegação exagerada: "O resultado é comprovado e garantido:
-- erradicamos a defasagem de leitura". O verificador devolveu **substantiated**.
--
-- O motivo é uma lacuna real da regra `absolute_language`: ela pune a palavra absoluta apenas
-- quando NÃO existe medição validada com evidência. Nesse ponto da jornada existia UMA medição
-- validada (32 pessoas) — e isso bastava para a palavra "erradicamos" passar.
--
-- Só que "comprovado" e "erradicamos" não são a mesma classe de afirmação. "Comprovado" afirma
-- PROVA, e uma medição validada com evidência é prova suficiente para a frase. "Erradicamos",
-- "100%", "zero", "neutro", "universalizamos" afirmam TOTALIDADE — e totalidade só pode ser
-- conferida contra um denominador: 32 de 60 elegíveis não é erradicação de nada.
--
-- Então a regra nova exige, para termo de totalidade, as duas coisas que o banco sabe conferir:
-- denominador vigente declarado com fonte, E medição validada cobrindo pelo menos 99% dele.
-- Continua determinística, continua contestável, e continua sem acusar ninguém de fraude.
INSERT INTO claim_rules(code, name_pt, severity, what_it_detects, why_it_matters) VALUES
  ('totality_claim_without_coverage', 'Afirmação de totalidade sem cobertura medida', 'serious',
   'O texto afirma totalidade (erradicamos, 100%, zero, neutro, universalizamos, todas as pessoas) '
   'sem que exista denominador vigente com fonte E medição validada cobrindo praticamente toda a '
   'população declarada.',
   'Totalidade é a única classe de afirmação que pode ser conferida por divisão: medido sobre '
   'elegível. "Erradicamos" com 32 de 60 elegíveis não é exagero de redação, é afirmação falsa — e '
   'era o caso que a regra de linguagem absoluta deixava passar quando havia qualquer medição '
   'validada no projeto.');
