"""Cofre de documentos: validação de upload (tamanho, extensão, assinatura binária/magic bytes, conteúdo ativo),
hash SHA-256, armazenamento privado com chave aleatória, antivírus, extração de texto e URLs temporárias."""
from __future__ import annotations

import io
import re
import uuid
import zipfile
import zlib

from ..http import ApiError

ALLOWED = {
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv", ".txt": "text/plain",
}
# Definido na inicialização (AppState): em development/test sem antivírus, arquivos 'pending_scan' contam como
# presentes para requisitos; em staging/production (ALLOW_UNSCANNED_DOWNLOADS=false) só 'clean' conta.
ACCEPT_UNSCANNED = False


def usable_statuses() -> tuple[str, ...]:
    return ("clean", "pending_scan") if ACCEPT_UNSCANNED else ("clean",)


# v0.35.0 (auditoria, FILE-02): a conferência antiga procurava o TEXTO literal (`/JavaScript`, `/JS `…) no arquivo bruto. Um
# PDF escreve o mesmo nome como `/J#61vaScript` (escape hexadecimal de nome, ISO 32000-1 §7.3.5) ou guarda o dicionário
# dentro de um fluxo de objetos COMPRIMIDO (`/Type /ObjStm`, §7.5.7) — e passava. Agora os NOMES são decodificados e os
# fluxos de objetos são descomprimidos (com teto, contra bomba de compressão) antes da conferência.
_PDF_ACTIVE_NAMES = frozenset({"JavaScript", "JS", "Launch", "EmbeddedFile", "EmbeddedFiles", "RichMedia", "XFA"})
_PDF_NAME = re.compile(rb"/((?:[^\x00\t\n\x0c\r ()<>\[\]{}/%#]|#[0-9A-Fa-f]{2})+)")
_PDF_STREAM = re.compile(rb">>\s*stream(?:\r\n|\n|\r)")
_PDF_INFLATE_CAP = 32 * 1024 * 1024


def _pdf_names(blob: bytes) -> set[str]:
    out = set()
    for m in _PDF_NAME.finditer(blob):
        raw = m.group(1)
        if b"#" in raw:
            raw = re.sub(rb"#([0-9A-Fa-f]{2})", lambda h: bytes([int(h.group(1), 16)]), raw)
        out.add(raw.decode("latin-1"))
    return out


def pdf_active_content(data: bytes) -> str | None:
    """Nome de conteúdo ativo encontrado no PDF (nos objetos soltos ou dentro de fluxos de objetos comprimidos), ou None."""
    found = _pdf_names(data) & _PDF_ACTIVE_NAMES
    if found:
        return sorted(found)[0]
    budget = _PDF_INFLATE_CAP
    for m in _PDF_STREAM.finditer(data):
        head = data[max(0, m.start() - 4096):m.start()]
        head = head[head.rfind(b" obj") + 1:] if b" obj" in head else head
        names = _pdf_names(head)
        if "ObjStm" not in names or "FlateDecode" not in names:
            continue
        end = data.find(b"endstream", m.end())
        body = data[m.end():end if end != -1 else len(data)]
        z = zlib.decompressobj()
        try:
            plain = z.decompress(body, budget + 1)
        except zlib.error:
            continue   # fluxo corrompido: o leitor de PDF também não o usaria
        if len(plain) > budget:
            return "ObjStm (fluxo de objetos grande demais para conferir)"
        budget -= len(plain)
        found = _pdf_names(plain) & _PDF_ACTIVE_NAMES
        if found:
            return sorted(found)[0]
    return None


def sniff(filename: str, data: bytes) -> str:
    """Retorna o MIME verificado pelo conteúdo ou levanta 422. Nunca confia no Content-Type do cliente."""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in ALLOWED:
        raise ApiError(422, "file_type_not_allowed", f"Tipo de arquivo não permitido. Aceitos: {', '.join(sorted(ALLOWED))}")
    if not data:
        raise ApiError(422, "empty_file", "Arquivo vazio")
    head = data[:16]
    ok = False
    if ext == ".pdf":
        ok = head.startswith(b"%PDF-")
        if ok and pdf_active_content(data):
            raise ApiError(422, "active_content", "PDF com conteúdo ativo (JavaScript/anexos/ações) não é aceito. Exporte novamente como PDF simples.")
    elif ext == ".png":
        ok = head.startswith(b"\x89PNG\r\n\x1a\n")
    elif ext in (".jpg", ".jpeg"):
        ok = head.startswith(b"\xff\xd8\xff")
    elif ext == ".webp":
        ok = head[:4] == b"RIFF" and data[8:12] == b"WEBP"
    elif ext in (".docx", ".xlsx"):
        if head.startswith(b"PK\x03\x04"):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    names = z.namelist()
                    if len(names) > 2000 or sum(i.file_size for i in z.infolist()) > 200 * 1024 * 1024:
                        raise ApiError(422, "suspicious_archive", "Arquivo compactado suspeito (zip bomb)")
                    prefix = "word/" if ext == ".docx" else "xl/"
                    ok = "[Content_Types].xml" in names and any(n.startswith(prefix) for n in names)
                    if any(n.lower().endswith("vbaproject.bin") for n in names):
                        raise ApiError(422, "active_content", "Documentos com macros não são aceitos")
            except zipfile.BadZipFile:
                ok = False
    elif ext in (".csv", ".txt"):
        if b"\x00" not in data:
            try:
                data.decode("utf-8")
                ok = True
            except UnicodeDecodeError:
                try:
                    data.decode("latin-1")
                    ok = True
                except UnicodeDecodeError:
                    ok = False
    if not ok:
        raise ApiError(422, "content_mismatch", "O conteúdo do arquivo não corresponde à extensão informada")
    return ALLOWED[ext]


def extract_text(mime: str, data: bytes, max_chars: int = 200_000) -> str | None:
    try:
        if mime == "application/pdf":
            from pypdf import PdfReader
            r = PdfReader(io.BytesIO(data))
            out = []
            for page in r.pages[:30]:
                out.append(page.extract_text() or "")
                if sum(len(x) for x in out) > max_chars:
                    break
            return "\n".join(out)[:max_chars] or None
        if mime in ("text/plain", "text/csv"):
            try:
                return data.decode("utf-8")[:max_chars]
            except UnicodeDecodeError:
                return data.decode("latin-1")[:max_chars]
        # v0.20.0 — `.docx` é ACEITO no envio (ver ALLOWED acima), `formats.py` declara no próprio
        # cabeçalho que lê docx e odt, os dois leitores existem e funcionam, e NENHUM dos dois
        # estava ligado aqui. Resultado prático: documento enviado em Word subia sem texto nenhum
        # extraído — e o classificador de documento, a busca e a sugestão de tipo recebiam vazio
        # sem que ninguém percebesse, porque "sem texto" é um resultado possível e silencioso.
        if mime in (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/msword"):
            from .formats import read_docx_text
            return read_docx_text(data, max_chars)
        if mime in ("application/vnd.oasis.opendocument.text", "application/x-vnd.oasis.opendocument.text"):
            from .formats import read_odt_text
            return read_odt_text(data, max_chars)
        if mime.startswith("image/"):
            try:  # OCR opcional (tesseract instalado no sistema)
                import pytesseract
                from PIL import Image
                langs = pytesseract.get_languages(config="")
                lang = "por" if "por" in langs else "eng"
                return pytesseract.image_to_string(Image.open(io.BytesIO(data)), lang=lang, timeout=20)[:max_chars] or None
            except Exception:  # noqa: BLE001 - OCR é melhor esforço: sem texto extraído o documento segue válido
                return None
    except Exception:  # noqa: BLE001 - extração de texto nunca derruba o envio do arquivo
        return None
    return None


def new_storage_key(org_id: str) -> str:
    return f"{org_id}/{uuid.uuid4().hex}"


def render_pdf(title: str, content: str, footer: str) -> bytes:
    """Gera PDF simples (texto) para assinatura de rascunhos. Usa reportlab (licença BSD)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    from xml.sax.saxutils import escape

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                            title=title, author="Plataforma Impacto", invariant=1)
    st = getSampleStyleSheet()
    story = [Paragraph(escape(title), st["Title"]), Spacer(1, 12)]
    for para in content.split("\n"):
        story.append(Paragraph(escape(para) if para.strip() else "&nbsp;", st["BodyText"]))
    story += [Spacer(1, 18), Paragraph(escape(footer), st["Italic"])]
    doc.build(story)
    return buf.getvalue()
