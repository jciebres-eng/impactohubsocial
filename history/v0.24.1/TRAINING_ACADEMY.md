# TRAINING_ACADEMY — Academia (v0.12.0)

**Escopo:** cursos curtos (módulos → aulas de texto, vídeo por URL com legendas/transcrição, atividade e **quiz**), trilhas de aprendizagem por perfil, progresso por pessoa e **certificado de conclusão não oficial**.

| Item | Como funciona | Prova |
|---|---|---|
| Matrícula | `POST /v1/help/courses/{slug}/enroll`; concluir aula sem matrícula → 409 | `Academy.test_enrollment_progress_quiz_and_certificate` |
| Quiz | gabarito em **tabela separada** (`lesson_quiz_keys`, sem acesso da aplicação); correção por função `SECURITY DEFINER`; API nunca devolve resposta certa | `test_quiz_key_never_leaves_the_server` (inclui SQL direto: 0 linhas) |
| Aprovação | `pass_score` por curso (padrão 70); reprovado não conclui a aula; tentativas contadas | idem |
| Certificado | só com **todas** as aulas concluídas, código verificável, **verificação pública** sem login (`GET /v1/help/certificates/{code}`), revogável por revisor com motivo (auditado) | `test_enrollment…` e E2E jornada 3 |
| Aviso | “Certificado de conclusão desta plataforma — não é diploma nem certificação oficial/reconhecida pelo MEC” (na página do curso e na verificação) | testes + E2E |
| Trilhas | `learning_paths` (curso/guia em ordem), por público | seed (`SeedContent`) cria 1 trilha de exemplo |
| Versão | curso tem `version`; **curso publicado não é editado no lugar** (limite declarado) | — |
| Acessibilidade de vídeo | campos de legenda e transcrição por aula; **a plataforma não hospeda vídeo** (URL externa) e **não verifica** se a legenda existe | — |

Não há: certificação reconhecida, pagamento por curso, avaliação discursiva, antiplágio, nem hospedagem de vídeo. O curso de exemplo é `demo=true`.
