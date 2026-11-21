"""Krok 1: konwersja dokumentu Worda do PDF (lokalnie, przez MS Word).

OCR w Eden AI przyjmuje tylko PDF albo obraz, więc .docx/.doc trzeba najpierw przekonwertować.
"""
from pathlib import Path

WORD_FORMATS = (".docx", ".doc", ".odt", ".rtf")


def to_pdf(src: str | Path, out_dir: str | Path, out_name: str | None = None) -> Path:
    """Zwraca ścieżkę do PDF. Plik PDF/obraz zwraca bez zmian."""
    src = Path(src)
    if src.suffix.lower() not in WORD_FORMATS:
        return src  # PDF lub obraz - bez konwersji

    import win32com.client

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = (out_dir / (out_name or (src.stem.strip() + ".pdf"))).resolve()
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    try:
        doc = word.Documents.Open(str(src.resolve()), ReadOnly=True)
        doc.SaveAs(str(dst), FileFormat=17)  # 17 = wdFormatPDF
        doc.Close(False)
    finally:
        word.Quit()
    return dst
