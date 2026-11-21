"""OCR dokumentu przez Eden AI v3.

Przepływ (wg dokumentacji Eden AI):
  1. .docx/.doc -> PDF (lokalnie, przez MS Word), bo OCR przyjmuje tylko PDF lub obraz.
  2. POST /v3/upload (multipart, pole "file", purpose="ocr")  -> file_id
  3a. async (domyślnie, wielostronicowe PDF):
        POST /v3/universal-ai/async  {"model": "ocr/ocr_async/<provider>", "input": {"file": file_id}}
        GET  /v3/universal-ai/async/<job_id>  aż status == success  -> output.raw_text
  3b. sync (--sync):
        POST /v3/universal-ai  {"model": "ocr/ocr/<provider>", "input": {"file": file_id}}  -> output.text

Użycie:
  python ocr_app.py [ścieżka_do_pliku] [--provider amazon] [--sync] [--language pl]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

BASE = "https://api.edenai.run/v3"
DEFAULT_FILE = (
    r"C:\Hackathon2026\Formularze-Wypakowane"
    r"\1. Wniosek o ustalenie numeru porządkowego nieruchomości - materiał referencyjny dla Uczestników do zadania"
    r"\Wniosek o ustalenie numeru porządkowego nieruchomości – wizualizacja formularza po cyfryzacji .docx"
)
OUT_DIR = Path(__file__).parent / "output"


def load_api_key() -> str:
    key = os.environ.get("EDENAI_API_KEY")
    env_file = Path(__file__).parent / "config_files" / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("EDENAI_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit("Brak klucza: ustaw EDENAI_API_KEY w zmiennej środowiskowej lub w pliku config_files/.env")
    return key


def to_pdf(src: Path) -> Path:
    """Konwertuje dokument Worda do PDF przez MS Word (COM)."""
    if src.suffix.lower() not in (".docx", ".doc", ".odt", ".rtf"):
        return src  # PDF / obraz idzie bez konwersji
    import win32com.client

    OUT_DIR.mkdir(exist_ok=True)
    dst = (OUT_DIR / (src.stem.strip() + ".pdf")).resolve()
    print(f"[1/3] Konwersja do PDF: {dst.name}")
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    try:
        doc = word.Documents.Open(str(src.resolve()), ReadOnly=True)
        doc.SaveAs(str(dst), FileFormat=17)  # 17 = wdFormatPDF
        doc.Close(False)
    finally:
        word.Quit()
    return dst


def check(resp: requests.Response) -> dict:
    try:
        data = resp.json()
    except ValueError:
        data = {"raw": resp.text}
    if not resp.ok:
        sys.exit(f"Błąd HTTP {resp.status_code}: {json.dumps(data, ensure_ascii=False, indent=2)}")
    return data


def upload(path: Path, headers: dict) -> str:
    print(f"[2/3] Upload: {path.name}")
    with open(path, "rb") as f:
        resp = requests.post(
            f"{BASE}/upload",
            headers=headers,
            files={"file": (path.name, f, "application/pdf" if path.suffix.lower() == ".pdf" else None)},
            data={"purpose": "ocr"},
            timeout=120,
        )
    data = check(resp)
    print(f"      file_id = {data['file_id']}")
    return data["file_id"]


def ocr_sync(file_id: str, provider: str, language: str | None, headers: dict) -> tuple[str, dict]:
    body = {"model": f"ocr/ocr/{provider}", "input": {"file": file_id}}
    if language:
        body["input"]["language"] = language
    data = check(requests.post(f"{BASE}/universal-ai", headers=headers, json=body, timeout=300))
    if data.get("status") != "success":
        sys.exit(f"OCR nie powiódł się: {json.dumps(data, ensure_ascii=False, indent=2)}")
    return data["output"].get("text", ""), data


def ocr_async(file_id: str, provider: str, headers: dict) -> tuple[str, dict]:
    body = {"model": f"ocr/ocr_async/{provider}", "input": {"file": file_id}}
    job = check(requests.post(f"{BASE}/universal-ai/async", headers=headers, json=body, timeout=120))
    job_id = job.get("public_id") or job.get("id") or job.get("job_id")
    if not job_id:
        sys.exit(f"Brak job_id w odpowiedzi: {json.dumps(job, ensure_ascii=False, indent=2)}")
    print(f"      job_id = {job_id}, czekam na wynik", end="", flush=True)
    for _ in range(120):  # do ~6 min
        data = check(requests.get(f"{BASE}/universal-ai/async/{job_id}", headers=headers, timeout=60))
        status = data.get("status")
        if status == "success":
            print(" gotowe")
            out = data.get("output") or {}
            return out.get("raw_text") or out.get("text", ""), data
        if status == "fail":
            print()
            sys.exit(f"OCR nie powiódł się: {json.dumps(data, ensure_ascii=False, indent=2)}")
        print(".", end="", flush=True)
        time.sleep(3)
    sys.exit("\nPrzekroczono czas oczekiwania na wynik OCR")


def main() -> None:
    ap = argparse.ArgumentParser(description="OCR pliku przez Eden AI")
    ap.add_argument("file", nargs="?", default=DEFAULT_FILE)
    ap.add_argument("--provider", default="amazon", help="np. amazon, microsoft, mistral, google")
    ap.add_argument("--sync", action="store_true", help="użyj synchronicznego ocr/ocr zamiast ocr_async")
    ap.add_argument("--language", default=None, help="kod języka dla trybu sync, np. pl")
    args = ap.parse_args()

    src = Path(args.file)
    if not src.exists():
        sys.exit(f"Plik nie istnieje: {src}")
    headers = {"Authorization": f"Bearer {load_api_key()}"}

    pdf = to_pdf(src)
    file_id = upload(pdf, headers)

    mode = "sync" if args.sync else "async"
    print(f"[3/3] OCR ({mode}, {args.provider})")
    if args.sync:
        text, raw = ocr_sync(file_id, args.provider, args.language, headers)
    else:
        text, raw = ocr_async(file_id, args.provider, headers)

    OUT_DIR.mkdir(exist_ok=True)
    stem = src.stem.strip()
    (OUT_DIR / f"{stem}.ocr.txt").write_text(text, encoding="utf-8")
    (OUT_DIR / f"{stem}.ocr.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano: {OUT_DIR / (stem + '.ocr.txt')}\n")
    print(text[:3000] + ("\n..." if len(text) > 3000 else ""))


if __name__ == "__main__":
    main()
