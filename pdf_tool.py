"""Document Tool: extract clean text from an uploaded supplier PDF."""
import io
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_CHARS = 30000      # keep prompts a sensible size
MIN_CHARS = 200        # below this the PDF is probably scanned or empty


def clean_text(text):
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)          # collapse spaces and tabs
    text = re.sub(r"\n{3,}", "\n\n", text)       # collapse blank lines
    return text.strip()


def extract_pdf_text(source):
    """source: a file path or a file-like object (e.g. a Streamlit upload).

    Returns {"text", "pages", "chars", "warnings", "ok"}. Never raises for bad files.
    """
    result = {"text": "", "pages": 0, "chars": 0, "warnings": [], "ok": False}
    try:
        if hasattr(source, "getvalue"):
            source = io.BytesIO(source.getvalue())
        reader = PdfReader(source)
        if reader.is_encrypted:
            result["warnings"].append("PDF is password-protected and could not be read.")
            return result
        pages = [(page.extract_text() or "") for page in reader.pages]
    except (PdfReadError, ValueError, OSError) as exc:
        result["warnings"].append(f"Could not read PDF: {exc}")
        return result

    text = clean_text("\n\n".join(pages))
    result["pages"] = len(pages)
    if len(text) < MIN_CHARS:
        result["warnings"].append(
            f"Very little text extracted ({len(text)} characters). The PDF may be scanned images.")
    if len(text) > MAX_CHARS:
        result["warnings"].append(f"Text truncated from {len(text)} to {MAX_CHARS} characters.")
        text = text[:MAX_CHARS]
    result["text"] = text
    result["chars"] = len(text)
    result["ok"] = len(text) >= MIN_CHARS
    return result


if __name__ == "__main__":
    import glob
    for path in sorted(glob.glob("sample_pdfs/*.pdf")):
        r = extract_pdf_text(path)
        print(f"{path}: pages={r['pages']} chars={r['chars']} ok={r['ok']} warnings={r['warnings']}")
    bad = extract_pdf_text(io.BytesIO(b"this is not a pdf"))
    print("Bad file test:", bad["ok"], bad["warnings"])
