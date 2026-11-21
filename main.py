"""Punkt startowy: plik wejściowy -> JSON.

  1. convert.to_pdf      - .docx -> PDF (lokalnie, MS Word)
  2. upload_file         - POST /v3/upload            -> file_id
  3. ocr.ocr_file        - POST /v3/universal-ai      -> tekst
  4. llm.text_to_json    - POST /v3/chat/completions  -> JSON
"""
import json
import sys
from pathlib import Path

from config import OUTPUT_DIR
from convert import to_pdf
from llm import text_to_json
from ocr import ocr_file
from upload_file import upload_file

INPUT_FILE = (
    r"C:\Hackathon2026\Formularze-Wypakowane"
    r"\1. Wniosek o ustalenie numeru porządkowego nieruchomości - materiał referencyjny dla Uczestników do zadania"
    r"\Wniosek o ustalenie numeru porządkowego nieruchomości – wizualizacja formularza po cyfryzacji .docx"
)


def main(input_file: str = INPUT_FILE):
    src = Path(input_file)
    if not src.exists():
        sys.exit(f"Plik nie istnieje: {src}")
    OUTPUT_DIR.mkdir(exist_ok=True)
    stem = src.stem.strip()

    print("[1/4] Konwersja do PDF...")
    pdf = to_pdf(src)
    print(f"      {pdf}")

    print("[2/4] Upload...")
    uploaded = upload_file(pdf)
    file_id = uploaded["file_id"]
    print(f"      file_id = {file_id}")

    print("[3/4] OCR...")
    ocr_result = ocr_file(file_id)
    text = ocr_result["output"]["text"]
    (OUTPUT_DIR / f"{stem}.ocr.txt").write_text(text, encoding="utf-8")
    print(f"      {len(text)} znaków tekstu")

    print("[4/4] LLM: tekst -> JSON...")
    data = text_to_json(text)
    out_file = OUTPUT_DIR / f"{stem}.json"
    out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nGotowe: {out_file}")
    return data


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else INPUT_FILE)
