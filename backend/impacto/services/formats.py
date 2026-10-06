"""Escrita de documentos em formatos de escritório, sem biblioteca nova.

Por que à mão: os registros npm/PyPI estão bloqueados neste ambiente, então `python-docx`/`openpyxl`/`odfpy` não podem
ser instalados. OOXML (.docx/.xlsx) e ODF (.odt/.ods) são ZIPs de XML — o mínimo válido é escrito aqui.

Formatos de SAÍDA: docx, xlsx, odt, ods, xml, csv, json, pdf (texto, com QR de verificação opcional).
Formatos de ENTRADA (extração de texto): docx e odt (lê o XML interno), além de csv/json/xml/txt/pdf que já existiam.

LIMITE DECLARADO: os arquivos são validados por testes que reabrem o ZIP e conferem o XML (estrutura, tipos de conteúdo,
conteúdo das células). **Não foram abertos no Microsoft Office nem no LibreOffice neste ambiente** — ver DOCUMENT_FORMATS.md.
Edição on-line colaborativa (Office na Web / Collabora / OnlyOffice) exige servidor WOPI e é DEPENDÊNCIA EXTERNA.
"""
from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from xml.sax.saxutils import escape, quoteattr, unescape

MAX_ROWS = 50_000
MAX_COLS = 256


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _col_name(idx: int) -> str:
    name = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        name = chr(65 + rem) + name
    return name


def _zip(entries: list[tuple[str, bytes]], *, first_stored: str | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries:
            if name == first_stored:                        # ODF exige 'mimetype' como 1ª entrada, sem compressão
                info = zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_STORED
                z.writestr(info, data)
            else:
                z.writestr(name, data)
    return buf.getvalue()


# ================================================================================ OOXML — .docx
def docx(title: str, blocks: list[tuple[str, str]], *, author: str = "Plataforma Impacto") -> bytes:
    """blocks: lista de (estilo, texto). Estilos: 'h1', 'h2', 'p', 'li', 'quote', 'spacer'."""
    styles = {"h1": "Heading1", "h2": "Heading2", "p": "Normal", "li": "ListParagraph", "quote": "Quote"}
    body = []
    for kind, text in blocks:
        if kind == "spacer":
            body.append("<w:p/>")
            continue
        style = styles.get(kind, "Normal")
        prefix = "• " if kind == "li" else ""
        runs = "".join(f'<w:r><w:t xml:space="preserve">{escape(prefix + line)}</w:t></w:r>'
                       for line in [text])
        body.append(f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>{runs}</w:p>')
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{"".join(body)}'
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr>'
        '</w:body></w:document>')
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
        '<w:pPr><w:spacing w:after="120"/></w:pPr><w:rPr><w:sz w:val="22"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
        '<w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>'
        '<w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
        '<w:pPr><w:spacing w:before="200" w:after="100"/></w:pPr>'
        '<w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
        '<w:pPr><w:ind w:left="360"/></w:pPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/>'
        '<w:pPr><w:ind w:left="360"/></w:pPr><w:rPr><w:i/></w:rPr></w:style>'
        '</w:styles>')
    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<dc:title>{escape(title)}</dc:title><dc:creator>{escape(author)}</dc:creator>'
        f'<cp:lastModifiedBy>{escape(author)}</cp:lastModifiedBy>'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{_now()}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{_now()}</dcterms:modified>'
        '</cp:coreProperties>')
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument'
        '.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument'
        '.wordprocessingml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '</Types>')
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/'
        'core-properties" Target="docProps/core.xml"/>'
        '</Relationships>')
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"'
        ' Target="styles.xml"/></Relationships>')
    return _zip([("[Content_Types].xml", content_types.encode()), ("_rels/.rels", rels.encode()),
                 ("docProps/core.xml", core.encode()), ("word/document.xml", document.encode()),
                 ("word/_rels/document.xml.rels", doc_rels.encode()), ("word/styles.xml", styles_xml.encode())])


# ================================================================================ OOXML — .xlsx
def xlsx(sheets: list[tuple[str, list[list]]]) -> bytes:
    """sheets: lista de (nome, linhas). A primeira linha é tratada como cabeçalho (negrito)."""
    if not sheets:
        sheets = [("Dados", [])]
    sheet_xmls: list[tuple[str, bytes]] = []
    overrides, sheet_defs, sheet_rels = [], [], []
    for i, (name, rows) in enumerate(sheets, start=1):
        if len(rows) > MAX_ROWS:
            raise ValueError(f"planilha com {len(rows)} linhas excede o limite de {MAX_ROWS}")
        out_rows = []
        for r, row in enumerate(rows, start=1):
            cells = []
            for col, value in enumerate(row[:MAX_COLS]):
                ref = f"{_col_name(col)}{r}"
                style = ' s="1"' if r == 1 else ""
                if value is None or value == "":
                    continue
                if isinstance(value, bool):
                    cells.append(f'<c r="{ref}"{style} t="b"><v>{1 if value else 0}</v></c>')
                elif isinstance(value, (int, float)):
                    cells.append(f'<c r="{ref}"{style}><v>{value}</v></c>')
                else:
                    cells.append(f'<c r="{ref}"{style} t="inlineStr"><is><t xml:space="preserve">'
                                 f'{escape(str(value))}</t></is></c>')
            out_rows.append(f'<row r="{r}">{"".join(cells)}</row>')
        sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                 f'<sheetData>{"".join(out_rows)}</sheetData></worksheet>')
        sheet_xmls.append((f"xl/worksheets/sheet{i}.xml", sheet.encode()))
        overrides.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.'
                         f'openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        safe = (name or f"Planilha{i}")[:31].replace(":", " ").replace("/", " ").replace("\\", " ")
        sheet_defs.append(f'<sheet name={quoteattr(safe)} sheetId="{i}" r:id="rId{i}"/>')
        sheet_rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                          f'relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
              '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
              '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
              '<borders count="1"><border/></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
              '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
              '</styleSheet>')
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
                ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f'<sheets>{"".join(sheet_defs)}</sheets></workbook>')
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               f'{"".join(sheet_rels)}'
               f'<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
               f'relationships/styles" Target="styles.xml"/></Relationships>')
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="xml" ContentType="application/xml"/>'
                     '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument'
                     '.spreadsheetml.sheet.main+xml"/>'
                     '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument'
                     '.spreadsheetml.styles+xml"/>'
                     f'{"".join(overrides)}</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'officeDocument" Target="xl/workbook.xml"/></Relationships>')
    return _zip([("[Content_Types].xml", content_types.encode()), ("_rels/.rels", rels.encode()),
                 ("xl/workbook.xml", workbook.encode()), ("xl/_rels/workbook.xml.rels", wb_rels.encode()),
                 ("xl/styles.xml", styles.encode()), *sheet_xmls])


# ================================================================================ ODF — .odt e .ods
_ODF_STYLES = (
    '<office:automatic-styles>'
    '<style:style style:name="Title" style:family="paragraph">'
    '<style:text-properties fo:font-size="20pt" fo:font-weight="bold"/></style:style>'
    '<style:style style:name="H2" style:family="paragraph">'
    '<style:text-properties fo:font-size="14pt" fo:font-weight="bold"/></style:style>'
    '</office:automatic-styles>')
_ODF_NS = (' xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
           ' xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"'
           ' xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
           ' xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"'
           ' xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"'
           ' xmlns:calcext="urn:org:documentfoundation:names:experimental:calc:xmlns:calcext:1.0"'
           ' office:version="1.3"')


def _odf(mimetype: str, content_body: str, title: str) -> bytes:
    content = (f'<?xml version="1.0" encoding="UTF-8"?><office:document-content{_ODF_NS}>'
               f'{_ODF_STYLES}<office:body>{content_body}</office:body></office:document-content>')
    styles = (f'<?xml version="1.0" encoding="UTF-8"?><office:document-styles{_ODF_NS}>'
              '<office:styles/></office:document-styles>')
    meta = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
            ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
            ' xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" office:version="1.3">'
            f'<office:meta><dc:title>{escape(title)}</dc:title>'
            f'<meta:generator>Plataforma Impacto</meta:generator>'
            f'<dc:date>{_now()}</dc:date></office:meta></office:document-meta>')
    manifest = ('<?xml version="1.0" encoding="UTF-8"?>'
                '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"'
                ' manifest:version="1.3">'
                f'<manifest:file-entry manifest:full-path="/" manifest:media-type="{mimetype}"/>'
                '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
                '<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>'
                '<manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>'
                '</manifest:manifest>')
    return _zip([("mimetype", mimetype.encode()), ("META-INF/manifest.xml", manifest.encode()),
                 ("content.xml", content.encode()), ("styles.xml", styles.encode()), ("meta.xml", meta.encode())],
                first_stored="mimetype")


def odt(title: str, blocks: list[tuple[str, str]]) -> bytes:
    paras = [f'<text:p text:style-name="Title">{escape(title)}</text:p>']
    for kind, text in blocks:
        if kind == "spacer":
            paras.append("<text:p/>")
        elif kind in ("h1", "h2"):
            paras.append(f'<text:h text:outline-level="{1 if kind == "h1" else 2}">{escape(text)}</text:h>')
        elif kind == "li":
            paras.append(f'<text:list><text:list-item><text:p>{escape(text)}</text:p></text:list-item></text:list>')
        else:
            paras.append(f'<text:p>{escape(text)}</text:p>')
    body = f'<office:text>{"".join(paras)}</office:text>'
    return _odf("application/vnd.oasis.opendocument.text", body, title)


def ods(sheets: list[tuple[str, list[list]]]) -> bytes:
    tables = []
    for name, rows in sheets or [("Dados", [])]:
        if len(rows) > MAX_ROWS:
            raise ValueError(f"planilha com {len(rows)} linhas excede o limite de {MAX_ROWS}")
        out = []
        for row in rows:
            cells = []
            for value in row[:MAX_COLS]:
                if value is None or value == "":
                    cells.append("<table:table-cell/>")
                elif isinstance(value, bool):
                    cells.append(f'<table:table-cell office:value-type="boolean" office:boolean-value='
                                 f'"{"true" if value else "false"}"><text:p>{"VERDADEIRO" if value else "FALSO"}'
                                 f'</text:p></table:table-cell>')
                elif isinstance(value, (int, float)):
                    cells.append(f'<table:table-cell office:value-type="float" office:value="{value}">'
                                 f'<text:p>{value}</text:p></table:table-cell>')
                else:
                    cells.append(f'<table:table-cell office:value-type="string"><text:p>{escape(str(value))}'
                                 f'</text:p></table:table-cell>')
            out.append(f'<table:table-row>{"".join(cells)}</table:table-row>')
        tables.append(f'<table:table table:name={quoteattr((name or "Dados")[:31])}>{"".join(out)}</table:table>')
    body = f'<office:spreadsheet>{"".join(tables)}</office:spreadsheet>'
    return _odf("application/vnd.oasis.opendocument.spreadsheet", body, (sheets or [("Dados", [])])[0][0])


# ================================================================================ XML e JSON
def xml(root: str, data, *, item: str = "item") -> bytes:
    """XML genérico para intercâmbio. Nomes de tag vêm de chaves saneadas — nunca de texto livre do usuário."""
    def tag_name(raw: str) -> str:
        clean = "".join(ch if (ch.isalnum() or ch in "_-.") else "_" for ch in str(raw))
        return clean if clean and not clean[0].isdigit() else f"_{clean}"

    def render(value, name: str) -> str:
        t = tag_name(name)
        if isinstance(value, dict):
            inner = "".join(render(v, k) for k, v in value.items())
            return f"<{t}>{inner}</{t}>"
        if isinstance(value, (list, tuple)):
            return f"<{t}>" + "".join(render(v, item) for v in value) + f"</{t}>"
        if value is None:
            return f'<{t} nil="true"/>'
        if isinstance(value, bool):
            return f"<{t}>{'true' if value else 'false'}</{t}>"
        return f"<{t}>{escape(str(value))}</{t}>"

    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + render(data, root)).encode()



# ================================================================================ PDF com QR de verificação
def pdf(title: str, blocks: list[tuple[str, str]], *, footer: str = "", verification_code: str | None = None,
        verification_url: str | None = None) -> bytes:
    """PDF de texto. Com código de verificação, imprime o QR e o código no fim — é o que torna o papel conferível."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer

    from ..trust import qr as QR

    class QrFlowable(Flowable):
        def __init__(self, text: str, size: float = 3.2 * cm):
            super().__init__()
            self.matrix = QR.matrix(text)
            self.size = size
            self.width = self.height = size

        def draw(self):
            n = len(self.matrix)
            module = self.size / (n + 8)
            self.canv.setFillColor(colors.black)
            for r in range(n):
                for c in range(n):
                    if self.matrix[r][c]:
                        self.canv.rect((c + 4) * module, self.size - (r + 5) * module, module, module,
                                       stroke=0, fill=1)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm,
                            bottomMargin=2 * cm, title=title, author="Plataforma Impacto", invariant=1)
    st = getSampleStyleSheet()
    story: list = [Paragraph(escape(title), st["Title"]), Spacer(1, 12)]
    for kind, text in blocks:
        if kind == "spacer":
            story.append(Spacer(1, 10))
        elif kind == "h1":
            story.append(Paragraph(escape(text), st["Heading1"]))
        elif kind == "h2":
            story.append(Paragraph(escape(text), st["Heading2"]))
        elif kind == "li":
            story.append(Paragraph("• " + escape(text), st["BodyText"]))
        else:
            story.append(Paragraph(escape(text) if text.strip() else "&nbsp;", st["BodyText"]))
    if footer:
        story += [Spacer(1, 18), Paragraph(escape(footer), st["Italic"])]
    if verification_code and verification_url:
        story += [Spacer(1, 18), Paragraph("Verificação pública", st["Heading2"]),
                  Paragraph(f"Código: <b>{escape(verification_code)}</b>", st["BodyText"]),
                  Paragraph(escape(verification_url), st["BodyText"]), Spacer(1, 6),
                  QrFlowable(verification_url),
                  Paragraph("Qualquer pessoa pode conferir a autenticidade deste documento com o código acima.",
                            st["Italic"])]
    doc.build(story)
    return buf.getvalue()


# ================================================================================ leitura (extração de texto)
def read_docx_text(data: bytes, max_chars: int = 200_000) -> str | None:
    import re
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            raw = z.read("word/document.xml").decode("utf-8", "replace")
    except (KeyError, zipfile.BadZipFile):
        return None
    raw = re.sub(r"</w:p>", "\n", raw)
    return unescape(re.sub(r"<[^>]+>", "", raw))[:max_chars].strip() or None


def read_odt_text(data: bytes, max_chars: int = 200_000) -> str | None:
    import re
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            raw = z.read("content.xml").decode("utf-8", "replace")
    except (KeyError, zipfile.BadZipFile):
        return None
    raw = re.sub(r"</text:(p|h)>", "\n", raw)
    return unescape(re.sub(r"<[^>]+>", "", raw))[:max_chars].strip() or None


EXPORT_FORMATS = ("pdf", "docx", "odt", "xlsx", "ods", "csv", "xml", "json")
WOPI_NOTE = ("Edição on-line colaborativa (Microsoft 365 na Web, Collabora Online, OnlyOffice) exige um servidor WOPI "
             "ou de documentos — é DEPENDÊNCIA EXTERNA e não está implementada. A plataforma exporta e importa os "
             "formatos acima, que abrem no Office e no LibreOffice instalados na máquina da pessoa.")
