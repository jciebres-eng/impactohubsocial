"""Gate 5 do pacote de execução: as dez conferências de segurança, cada uma EXECUTADA.

O QUE ESTE ARQUIVO NÃO É

Não é um pentest. Não há ferramenta destrutiva aqui, nada roda contra produção, e nenhum resultado
daqui substitui teste de intrusão por terceiro. A regra permanente deste projeto vale inteira:
NENHUM sistema conectado à internet pode receber garantia de ser impossível de invadir, e este
arquivo não a dá.

O que ele faz é fechar a distância entre "a defesa existe no código" e "a defesa foi exercitada".
Das dez linhas do Gate 5, seis já tinham cobertura sob outro nome (SSRF em
`test_v0130_integrations.py`, CSRF e cookies em `test_v0150_security.py`, multilocação em
`test_security_tenancy.py`, upload em `test_v0120_hardening.py`). Quatro não tinham teste que as
nomeasse — travessia de caminho, redirecionamento aberto, injeção de cabeçalho e desserialização — e
é delas que este arquivo trata, junto com a ampliação do SSRF para IPv6 e codificações alternativas.

SAST E SEGREDO SÃO EXECUTADOS, SCA NÃO É

`pyproject.toml` já seleciona as regras `S` do ruff (flake8-bandit): SAST roda em cada lint e passa.
A varredura de segredo roda aqui, por `scripts/secrets_scan.py`, porque gitleaks não existe neste
ambiente. SCA exige base de vulnerabilidade viva, e nem PyPI nem a API de avisos do GitHub são
alcançáveis daqui — está declarado em `BLOCKERS.md` como D-SUP2 e NÃO é afirmado como executado.
"""
from __future__ import annotations

import ast
import subprocess
import sys
import unittest

from tests.support import Client, ROOT, new_account, server

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


class TheSsrfGuardRefusesEveryWayOfSpellingTheInsideTests(unittest.TestCase):
    """Um bloqueio de SSRF que só entende `169.254.169.254` não bloqueia SSRF.

    As formas de escrever "dentro" são muitas: IPv6 de loopback, IPv6 mapeado em IPv4, link-local
    IPv6 (onde ficam os metadados em algumas nuvens), inteiro decimal, octal, e o host que resolve
    para dentro. A guarda certa resolve o nome e julga o IP — não o texto.
    """

    def setUp(self):
        from impacto.adapters.http_client import check_destination
        self.verifica = check_destination

    def _recusa(self, url: str, porque: str):
        with self.subTest(url=url):
            with self.assertRaises((ValueError, OSError), msg=f"{url} deveria ser recusado: {porque}"):
                self.verifica(url)

    def test_cloud_metadata_endpoints_are_refused_in_every_notation(self):
        for url, porque in (
            ("https://169.254.169.254/latest/meta-data/", "metadados AWS/GCP, link-local"),
            ("https://[fd00:ec2::254]/latest/meta-data/", "metadados IPv6 da AWS, endereço privado"),
            ("https://[::ffff:169.254.169.254]/", "link-local escrito como IPv6 mapeado"),
            ("https://2852039166/", "169.254.169.254 em inteiro decimal"),
            ("https://0251.0376.0251.0376/", "link-local em octal"),
        ):
            self._recusa(url, porque)

    def test_private_ranges_are_refused_in_every_environment(self):
        for url, porque in (
            ("https://10.0.0.5/", "rede privada classe A"),
            ("https://192.168.1.1/", "rede privada doméstica"),
            ("https://172.16.0.1/", "rede privada classe B"),
            ("https://[fe80::1]/", "link-local IPv6"),
            ("https://0.0.0.0/", "endereço não especificado"),
            ("https://[fc00::1]/", "unique local IPv6"),
        ):
            self._recusa(url, porque)

    def test_loopback_is_allowed_only_in_development_and_refused_in_production(self):
        """A isenção de loopback existe para o desenvolvedor, e tem que MORRER em produção.

        `check_destination` libera loopback quando `IMPACTO_ENV` é `development` ou `test` — sem
        isso, nenhum teste local falaria com um dublê em `127.0.0.1`. O risco é a isenção sobreviver
        ao deploy: em produção, loopback é a porta para todo serviço interno da máquina. Aqui se
        confere a isenção NOS DOIS SENTIDOS, trocando a variável de ambiente.
        """
        import os
        from unittest import mock
        loopbacks = ("https://127.0.0.1/", "https://[::1]/", "https://[::ffff:127.0.0.1]/")
        with mock.patch.dict(os.environ, {"IMPACTO_ENV": "test"}):
            for url in loopbacks[:1]:
                self.verifica(url)  # não levanta: é a isenção de desenvolvimento, e ela é intencional
        for ambiente in ("production", "staging"):
            with mock.patch.dict(os.environ, {"IMPACTO_ENV": ambiente}):
                for url in loopbacks:
                    with self.subTest(ambiente=ambiente, url=url):
                        with self.assertRaises((ValueError, OSError),
                                               msg=f"{url} aceito em {ambiente}: a isenção de "
                                                   "desenvolvimento sobreviveu ao deploy"):
                            self.verifica(url)

    def test_only_https_reaches_the_outside(self):
        for url, porque in (
            ("http://exemplo.org/", "http simples para host externo"),
            ("file:///etc/passwd", "esquema de arquivo local"),
            ("gopher://exemplo.org/", "esquema que permite falar com serviço arbitrário"),
            ("ftp://exemplo.org/", "esquema sem TLS"),
        ):
            self._recusa(url, porque)

    def test_redirects_are_never_followed(self):
        """Seguir redirecionamento devolve o controle do destino a quem responde — é SSRF de segunda etapa."""
        import urllib.request
        from impacto.adapters import http_client
        for h in http_client._OPENER.handlers:
            if isinstance(h, urllib.request.HTTPRedirectHandler):
                self.assertIsNone(h.redirect_request("req", "fp", 302, "msg", {}, "https://127.0.0.1/"),
                                  "o manipulador devolveu uma requisição: o redirecionamento seria seguido")
                return
        self.fail("nenhum manipulador de redirecionamento instalado: o padrão do urllib SEGUE redirecionamento")

    def test_the_guard_does_not_depend_on_the_caller_remembering_to_call_it(self):
        """A guarda roda no TRANSPORTE, não na rota: uma rota nova não pode esquecer de verificar."""
        fonte = (ROOT / "backend" / "impacto" / "adapters" / "http_client.py").read_text(encoding="utf-8")
        transporte = fonte[fonte.index("def urllib_transport"):]
        self.assertIn("check_destination(url)", transporte.split("\n\n")[0],
                      "o transporte não verifica o destino; a verificação na rota é opcional por natureza")


class PathTraversalNeverEscapesTheOrganizationFolderTests(unittest.TestCase):
    """Travessia de caminho: o nome do arquivo vem de fora e nunca entra na chave de armazenamento."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc", compliance="approved")

    def test_the_storage_key_is_generated_and_never_taken_from_the_filename(self):
        from impacto.services.documents import new_storage_key
        chave = new_storage_key("11111111-1111-1111-1111-111111111111")
        self.assertTrue(chave.startswith("11111111-1111-1111-1111-111111111111/"))
        self.assertNotIn("..", chave)
        # Duas chamadas nunca colidem: a chave é aleatória, não derivada do nome enviado.
        self.assertNotEqual(chave, new_storage_key("11111111-1111-1111-1111-111111111111"))

    def test_a_filename_full_of_traversal_does_not_escape_anywhere(self):
        for nome in ("../../../../etc/passwd.pdf", "..\\..\\windows\\system32\\x.pdf",
                     "....//....//etc/shadow.pdf", "/absoluto/etc/passwd.pdf",
                     "arquivo\x00oculto.pdf"):
            with self.subTest(nome=nome):
                r = self.org.upload("/v1/documents", nome, PDF,
                                    {"doc_type": "outro", "title": "Travessia"})
                # Aceitar é permitido — o que não é permitido é o nome virar caminho.
                if r.status in (200, 201):
                    doc = self.org.get(f"/v1/documents/{r.json['id']}")
                    self.assertEqual(doc.status, 200, doc.body)
                    bruto = str(doc.json)
                    self.assertNotIn("..", bruto.replace("...", ""),
                                     f"o nome {nome!r} sobreviveu como caminho relativo")
                    self.assertNotIn("/etc/", bruto)
                    self.assertNotIn("\x00", bruto)
                else:
                    self.assertGreaterEqual(r.status, 400, r.body)


class NoRouteTurnsIntoAnOpenRedirectTests(unittest.TestCase):
    """Redirecionamento aberto: um `Location` para fora transforma o domínio em trampolim de phishing."""

    @classmethod
    def setUpClass(cls):
        server()

    def test_no_route_accepts_a_destination_from_the_query_string(self):
        """A conferência é no CÓDIGO: nenhuma rota lê parâmetro de destino para montar `Location`."""
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        suspeitos = {"next", "redirect", "redirect_uri", "return_to", "returnTo", "continue",
                     "callback", "url", "destination", "goto"}
        achados = []
        for r in ROUTES:
            campos = set(getattr(r.query, "model_fields", {}) or {})
            for nome in campos & suspeitos:
                achados.append(f"{r.method} {r.path} aceita ?{nome}=")
        # `redirect_uri` do OIDC é a exceção legítima, e é conferida contra lista declarada.
        achados = [a for a in achados if "/oidc" not in a and "/auth/sso" not in a]
        self.assertEqual(achados, [], f"rotas que aceitam destino externo: {achados}")

    def test_responses_that_redirect_only_point_inside(self):
        """Toda resposta 3xx do produto aponta para caminho relativo, nunca para outro domínio."""
        fontes = list((ROOT / "backend" / "impacto").rglob("*.py"))
        externos = []
        for f in fontes:
            texto = f.read_text(encoding="utf-8")
            for i, linha in enumerate(texto.splitlines(), start=1):
                if "RedirectResponse" not in linha and '"location"' not in linha.lower():
                    continue
                if "http://" in linha or "https://" in linha:
                    externos.append(f"{f.name}:{i} {linha.strip()[:90]}")
        permitidos = [e for e in externos if "oidc" in e.lower() or "sso" in e.lower()
                      or "PUBLIC_BASE_URL" in e or "public_base_url" in e]
        self.assertEqual([e for e in externos if e not in permitidos], [],
                         "redirecionamento com destino absoluto fora do OIDC/base pública")


class HeaderInjectionIsImpossibleTests(unittest.TestCase):
    """Injeção de cabeçalho: CRLF num valor parte a resposta em duas e deixa escrever a segunda."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc", compliance="approved")

    def test_a_filename_with_crlf_does_not_split_the_response(self):
        nome = "normal\r\nX-Injetado: sim\r\n\r\n<html>oi</html>.pdf"
        r = self.org.upload("/v1/documents", nome, PDF, {"doc_type": "outro", "title": "CRLF"})
        if r.status in (200, 201):
            baixa = self.org.get(f"/v1/documents/{r.json['id']}/download")
            cabecalhos = {k.lower(): v for k, v in (baixa.headers or {}).items()}
            self.assertNotIn("x-injetado", cabecalhos, "CRLF no nome do arquivo criou cabeçalho novo")
            for valor in cabecalhos.values():
                self.assertNotIn("\n", str(valor))
                self.assertNotIn("\r", str(valor))
        else:
            self.assertGreaterEqual(r.status, 400, r.body)

    def test_the_server_refuses_a_request_header_carrying_crlf(self):
        """Pelo SOCKET, porque é assim que um atacante faz.

        O cliente HTTP do Python se recusa a montar um cabeçalho com CRLF — o que é correto e
        inútil como teste: prova que o urllib é bem comportado, não que o servidor é. Quem injeta
        abre um socket e escreve os bytes. Então é o que este teste faz.
        """
        import socket as sock
        from urllib.parse import urlsplit
        base = urlsplit(server()["base"])
        bruto = (
            "GET /v1/meta/platform-status HTTP/1.1\r\n"
            f"Host: {base.hostname}:{base.port}\r\n"
            "X-Correlation-Id: abc\r\nX-Injetado: sim\r\n"
            "Connection: close\r\n\r\n"
        ).encode()
        with sock.create_connection((base.hostname, base.port), timeout=10) as s:
            s.sendall(bruto)
            pedacos = []
            while True:
                b = s.recv(65536)
                if not b:
                    break
                pedacos.append(b)
        resposta = b"".join(pedacos).decode("latin-1")
        cabecalho, _, _ = resposta.partition("\r\n\r\n")
        linhas = [l.lower() for l in cabecalho.split("\r\n")]
        # Duas saídas aceitáveis, e ambas seguras: o servidor recusa a requisição malformada, ou
        # trata o CRLF como fim do cabeçalho e simplesmente não ecoa nada de volta. O que NÃO é
        # aceitável é `x-injetado` aparecer na RESPOSTA — aí o cabeçalho de entrada virou de saída.
        self.assertFalse(any(l.startswith("x-injetado") for l in linhas),
                         f"CRLF da requisição virou cabeçalho da resposta:\n{cabecalho[:500]}")
        self.assertTrue(linhas and linhas[0].startswith("http/1."), f"resposta malformada: {linhas[:3]}")


class NothingInThisCodebaseDeserializesUntrustedInputTests(unittest.TestCase):
    """Desserialização: `pickle`, `yaml.load`, `eval` e `exec` sobre dado de fora são execução remota.

    A conferência é estrutural e vale para código que ainda não existe: qualquer arquivo novo que
    importe `pickle` ou chame `eval` reprova aqui, e quem precisar de verdade terá que declarar a
    exceção com motivo escrito.
    """

    #: Exceções declaradas, com motivo. Lista vazia é o estado desejado.
    PERMITIDO: dict[str, str] = {}

    def test_no_module_imports_pickle_marshal_or_shelve(self):
        proibidos = {"pickle", "cPickle", "marshal", "shelve", "dill"}
        achados = []
        for f in (ROOT / "backend" / "impacto").rglob("*.py"):
            arvore = ast.parse(f.read_text(encoding="utf-8"))
            for no in ast.walk(arvore):
                if isinstance(no, ast.Import):
                    achados += [f"{f.name}: import {a.name}" for a in no.names
                                if a.name.split(".")[0] in proibidos]
                elif isinstance(no, ast.ImportFrom) and (no.module or "").split(".")[0] in proibidos:
                    achados.append(f"{f.name}: from {no.module}")
        self.assertEqual([a for a in achados if a not in self.PERMITIDO], [], achados)

    def test_no_module_calls_eval_or_exec(self):
        achados = []
        for f in (ROOT / "backend" / "impacto").rglob("*.py"):
            arvore = ast.parse(f.read_text(encoding="utf-8"))
            for no in ast.walk(arvore):
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) \
                        and no.func.id in ("eval", "exec", "compile"):
                    achados.append(f"{f.name}:{no.lineno} {no.func.id}()")
        self.assertEqual([a for a in achados if a not in self.PERMITIDO], [], achados)

    def test_xml_parsing_goes_through_the_hardened_parser(self):
        """XML com entidade externa lê arquivo do servidor. `defusedxml` é o que recusa."""
        achados = []
        for f in (ROOT / "backend" / "impacto").rglob("*.py"):
            texto = f.read_text(encoding="utf-8")
            if "xml.etree" in texto and "defusedxml" not in texto:
                achados.append(f.name)
        self.assertEqual(achados, [], f"XML sem parser endurecido em {achados}")


class PrototypePollutionAndMassAssignmentAreRefusedTests(unittest.TestCase):
    """Chave especial no corpo JSON não vira atributo, e campo a mais é recusado em vez de ignorado."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc", compliance="approved")

    def test_special_keys_in_the_body_are_refused_not_absorbed(self):
        for chave in ("__proto__", "constructor", "prototype", "__class__", "__init__"):
            with self.subTest(chave=chave):
                r = self.org.post("/v1/projects", {
                    "title": "Projeto", "problem": "Problema declarado", "objectives": "Objetivo",
                    "methodology": "Método", "territory": "MT", chave: {"x": 1}})
                self.assertEqual(r.status, 422, f"{chave} não foi recusada: {r.body}")

    def test_a_field_the_schema_does_not_declare_is_refused(self):
        r = self.org.post("/v1/projects", {
            "title": "Projeto", "problem": "Problema declarado", "objectives": "Objetivo",
            "methodology": "Método", "territory": "MT", "org_id": "11111111-1111-1111-1111-111111111111"})
        self.assertEqual(r.status, 422, f"campo extra aceito: {r.body}")


class SqlInjectionPayloadsAreDataNotCodeTests(unittest.TestCase):
    """Injeção de SQL: o driver parametriza, e a prova é que a carga volta como TEXTO."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc", compliance="approved")

    CARGAS = ("' OR '1'='1", "'; DROP TABLE projects; --", "1' UNION SELECT NULL--",
              "'||pg_sleep(5)||'", "\\'; SELECT version(); --", "%27%20OR%201=1")

    def test_a_payload_in_a_search_field_finds_nothing_and_breaks_nothing(self):
        from urllib.parse import quote
        for carga in self.CARGAS:
            with self.subTest(busca=carga):
                r = self.org.get(f"/v1/projects?q={quote(carga)}")
                self.assertIn(r.status, (200, 422), r.body)
                if r.status == 200:
                    self.assertEqual(r.json["items"], [], "a carga casou com algo: não foi tratada como texto")

    def test_the_table_is_still_there_afterwards(self):
        r = self.org.post("/v1/projects", {"title": "Depois da carga", "problem": "Problema declarado",
                                           "objectives": "Objetivo", "methodology": "Método", "territory": "MT"})
        self.assertIn(r.status, (200, 201), f"a tabela de projetos não respondeu depois das cargas: {r.body}")

    def test_the_payload_stored_as_a_title_comes_back_identical(self):
        """Se voltou idêntico, foi dado. Se voltou alterado, alguém escapou — e escapar é o caminho errado."""
        carga = "'; DROP TABLE projects; --"
        r = self.org.post("/v1/projects", {"title": carga, "problem": "Problema declarado",
                                           "objectives": "Objetivo", "methodology": "Método", "territory": "MT"})
        self.assertIn(r.status, (200, 201), r.body)
        self.assertEqual(self.org.get(f"/v1/projects/{r.json['id']}").json["title"], carga)


class EveryResponseCarriesTheSecurityHeadersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc", compliance="approved")

    EXIGIDOS = {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "strict-origin-when-cross-origin",
        "cross-origin-opener-policy": "same-origin",
    }

    def test_public_private_and_error_responses_all_carry_them(self):
        for descricao, resposta in (
            ("pública", Client().get("/v1/meta/platform-status")),
            ("autenticada", self.org.get("/v1/me/context")),
            ("erro 404", self.org.get("/v1/projects/11111111-1111-1111-1111-111111111111")),
            ("erro 422", self.org.post("/v1/projects", {"title": ""})),
        ):
            cabecalhos = {k.lower(): v for k, v in (resposta.headers or {}).items()}
            for nome, valor in self.EXIGIDOS.items():
                with self.subTest(resposta=descricao, cabecalho=nome):
                    self.assertEqual(cabecalhos.get(nome), valor,
                                     f"resposta {descricao} sem {nome}")

    def test_the_content_security_policy_has_no_escape_hatch(self):
        csp = {k.lower(): v for k, v in (self.org.get("/v1/me/context").headers or {}).items()}.get(
            "content-security-policy", "")
        self.assertTrue(csp, "sem CSP")
        for furo in ("unsafe-inline", "unsafe-eval", "*"):
            self.assertNotIn(furo, csp, f"CSP contém {furo}")
        for exigido in ("default-src 'self'", "object-src 'none'", "frame-ancestors 'none'",
                        "base-uri 'self'", "form-action 'self'"):
            self.assertIn(exigido, csp, f"CSP sem {exigido}")

    def test_hsts_is_tied_to_the_hardened_setting_and_not_to_chance(self):
        """HSTS num ambiente sem TLS trancaria o desenvolvedor fora. A ligação é a configuração."""
        from impacto.app import SecurityHeaders
        nomes = lambda h: {k.decode() for k, _ in h}  # noqa: E731
        self.assertIn("strict-transport-security", nomes(SecurityHeaders(None, hardened=True).headers))
        self.assertNotIn("strict-transport-security", nomes(SecurityHeaders(None, hardened=False).headers))


class TheSecretsScanRunsAndFindsNothingTests(unittest.TestCase):
    """Varredura de segredo executada aqui, porque gitleaks não existe neste ambiente.

    A regra permanente do projeto proíbe senha, chave de API, token, segredo e certificado privado em
    entregável. Esta é a conferência dessa regra, e ela roda em cada suíte.
    """

    def test_the_repository_carries_no_secret(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "secrets_scan.py")],
                           capture_output=True, text=True, cwd=ROOT, timeout=300)
        self.assertEqual(r.returncode, 0, f"varredura de segredo acusou:\n{r.stdout[-4000:]}\n{r.stderr[-2000:]}")

    def test_the_scan_can_actually_find_a_secret(self):
        """Controle negativo. Sem ele, uma varredura que não acha NADA é indistinguível de uma que
        não PROCURA nada — e as duas passam verde para sempre.

        O arquivo plantado é temporário, fica fora do pacote, e é removido mesmo se a asserção
        falhar. `git add -N` o torna rastreado sem gravar conteúdo no índice, porque a varredura só
        olha arquivo rastreado (é o que vai para o ZIP).
        """
        from impacto.engines.registry import ENGINES  # noqa: F401  (garante que o pacote importa)
        plantado = ROOT / "backend" / "impacto" / "_controle_negativo_da_varredura.py"
        # As amostras são MONTADAS em pedaços, de propósito. Escritas inteiras, elas seriam
        # segredos literais DENTRO deste arquivo — e a varredura, fazendo seu trabalho, acusaria o
        # próprio teste que a verifica. Foi o que aconteceu na primeira execução completa. Isentar
        # este arquivo seria a saída errada: abriria um buraco permanente num teste de segurança.
        amostras = (
            ("AKIA" + "2J4QRSTUVWXYZ7BC", "chave de acesso da AWS"),
            ("ghp" + "_aB3dEfGhIjKlMnOpQrStUvWxYz0123456789", "token do GitHub"),
            ("sk" + "_live_51H8xQwErTyUiOpAsDfGhJkL", "chave do Stripe"),
            ("-----BEGIN " + "RSA PRIVATE KEY-----", "chave privada"),
        )
        conteudo = "\n".join(f'VALOR_{i} = "{v}"' for i, (v, _) in enumerate(amostras))

        def limpar():
            plantado.unlink(missing_ok=True)
            # `git rm --cached`, e não `git reset`: o arquivo entrou no índice por `git add -N`
            # (intenção de adicionar) e foi removido do disco, e `git reset` deixa a entrada como
            # " D" — a árvore fica suja e o Gate 10 exige Git limpo. Descoberto depois da primeira
            # execução completa, que deixou o repositório com uma remoção pendente.
            subprocess.run(["git", "rm", "--cached", "--ignore-unmatch", "-q", str(plantado)],
                           cwd=ROOT, capture_output=True)
        self.addCleanup(limpar)

        plantado.write_text(conteudo + "\n", encoding="utf-8")
        subprocess.run(["git", "add", "-N", str(plantado)], cwd=ROOT, capture_output=True, check=True)
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "secrets_scan.py")],
                           capture_output=True, text=True, cwd=ROOT, timeout=300)
        self.assertEqual(r.returncode, 1, "a varredura não acusou NENHUM dos segredos plantados")
        for valor, descricao in amostras:
            self.assertIn(valor[:18], r.stdout, f"não encontrou o segredo plantado: {descricao}")


class SastIsSelectedInTheLintConfigurationTests(unittest.TestCase):
    """SAST não é ferramenta à parte aqui: as regras `S` do ruff são o flake8-bandit.

    Isto não roda o ruff (o CI roda); confere que a SELEÇÃO existe, para que ninguém a remova sem a
    suíte acusar. Uma configuração que deixa de selecionar `S` desliga o SAST silenciosamente.
    """

    def test_the_bandit_rules_are_selected_and_the_ignores_are_justified(self):
        texto = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
        selecao = texto[texto.index("select = ["):texto.index("]", texto.index("select = ["))]
        self.assertIn('"S"', selecao, "as regras de segurança do ruff (flake8-bandit) não estão selecionadas")
        linha_ignore = next(l for l in texto.splitlines() if l.strip().startswith("ignore = ["))
        for regra in ("S101", "S608"):
            if regra in linha_ignore:
                self.assertIn("#", linha_ignore, f"{regra} ignorada sem motivo escrito")


class TheGitleaksIgnoreIsNarrowAndExplainedTests(unittest.TestCase):
    """`.gitleaksignore` só pode liberar achados UM A UM, cada grupo com motivo escrito.

    v0.24.0: a primeira execução real do gitleaks no CI (a action exigia licença e nunca tinha
    rodado) achou 15 itens no histórico; os 15 foram conferidos — senhas e segredos fictícios de
    teste, um placeholder de Stripe, a lista de senhas que o cadastro recusa, uma linha de texto.
    Liberar por arquivo ou por regra esconderia o próximo segredo de verdade nesses mesmos lugares.
    """

    @classmethod
    def setUpClass(cls):
        cls.linhas = (ROOT / ".gitleaksignore").read_text(encoding="utf-8").splitlines()

    def test_every_entry_is_a_single_finding_fingerprint(self):
        entradas = [l for l in self.linhas if l.strip() and not l.startswith("#")]
        self.assertEqual(len(entradas), 15, "achado novo liberado? revise e atualize este número junto")
        for e in entradas:
            self.assertRegex(e, r"^[0-9a-f]{40}:[^:*]+:[a-z0-9-]+:\d+$",
                             f"entrada não é impressão digital de UM achado: {e}")
        self.assertFalse(any("*" in e for e in entradas), "curinga em .gitleaksignore")

    def test_every_group_has_a_written_reason(self):
        grupo_tem_motivo = False
        for l in self.linhas:
            if l.startswith("# ["):
                grupo_tem_motivo = True
            elif l.strip() and not l.startswith("#"):
                self.assertTrue(grupo_tem_motivo, f"entrada sem grupo com motivo acima: {l}")
            elif not l.strip():
                grupo_tem_motivo = False

    def test_ci_runs_the_binary_not_the_licensed_action(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertNotIn("uses: gitleaks/gitleaks-action", ci, "a action exige licença e derruba o CI inteiro")
        self.assertIn("./gitleaks git", ci)
        self.assertIn("sha256sum -c", ci, "o binário tem de ser conferido contra os checksums da release")
