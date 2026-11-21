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
  python ocr_app.py [ścieżka_do_pliku] [--provider amazon] [--sync | --no-sync] [--language pl]

Ustawienia: argumenty CLI > config_files/ocr_app.json (albo --config <plik>) > DEFAULTS poniżej.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

from config import API, CONFIG_DIR, OCR_ASYNC_URL, OCR_URL, UPLOAD_URL, resolve_settings
DEFAULT_FILE = (
    r"C:\Hackathon2026\Formularze-Wypakowane"
    r"\1. Wniosek o ustalenie numeru porządkowego nieruchomości - materiał referencyjny dla Uczestników do zadania"
    r"\Wniosek o ustalenie numeru porządkowego nieruchomości – wizualizacja formularza po cyfryzacji .docx"
)
OUT_DIR = Path(__file__).parent / "output"

DEFAULT_CONFIG_FILE = CONFIG_DIR / "ocr_app.json"
DEFAULTS = {
    "file": DEFAULT_FILE,
    "provider": "amazon",
    "sync": False,
    "language": None,
    "output_dir": str(OUT_DIR),
    "poll_interval_s": 3,
    "poll_max_attempts": 120,
}


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
            UPLOAD_URL,
            headers=headers,
            files={"file": (path.name, f, "application/pdf" if path.suffix.lower() == ".pdf" else None)},
            data={"purpose": API["upload_purpose"]},
            timeout=API["upload_timeout_s"],
        )
    data = check(resp)
    print(f"      file_id = {data['file_id']}")
    return data["file_id"]


def ocr_sync(file_id: str, provider: str, language: str | None, headers: dict) -> tuple[str, dict]:
    body = {"model": f"ocr/ocr/{provider}", "input": {"file": file_id}}
    if language:
        body["input"]["language"] = language
    data = check(requests.post(OCR_URL, headers=headers, json=body, timeout=API["ocr_timeout_s"]))
    if data.get("status") != "success":
        sys.exit(f"OCR nie powiódł się: {json.dumps(data, ensure_ascii=False, indent=2)}")
    return data["output"].get("text", ""), data


def ocr_async(file_id: str, provider: str, headers: dict,
              poll_interval_s: float = 3, poll_max_attempts: int = 120) -> tuple[str, dict]:
    body = {"model": f"ocr/ocr_async/{provider}", "input": {"file": file_id}}
    job = check(requests.post(OCR_ASYNC_URL, headers=headers, json=body,
                              timeout=API["ocr_async_create_timeout_s"]))
    job_id = job.get("public_id") or job.get("id") or job.get("job_id")
    if not job_id:
        sys.exit(f"Brak job_id w odpowiedzi: {json.dumps(job, ensure_ascii=False, indent=2)}")
    print(f"      job_id = {job_id}, czekam na wynik", end="", flush=True)
    for _ in range(poll_max_attempts):
        data = check(requests.get(f"{OCR_ASYNC_URL}/{job_id}", headers=headers,
                                  timeout=API["ocr_async_poll_timeout_s"]))
        status = data.get("status")
        if status == "success":
            print(" gotowe")
            out = data.get("output") or {}
            return out.get("raw_text") or out.get("text", ""), data
        if status == "fail":
            print()
            sys.exit(f"OCR nie powiódł się: {json.dumps(data, ensure_ascii=False, indent=2)}")
        print(".", end="", flush=True)
        time.sleep(poll_interval_s)
    sys.exit("\nPrzekroczono czas oczekiwania na wynik OCR")


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="OCR pliku przez Eden AI")
    ap.add_argument("file", nargs="?", default=None)
    ap.add_argument("-c", "--config", type=Path, default=None,
                    help="plik konfiguracyjny JSON (domyślnie config_files/ocr_app.json, jeśli istnieje)")
    ap.add_argument("--provider", default=None, help="np. amazon, microsoft, mistral, google")
    ap.add_argument("--sync", action=argparse.BooleanOptionalAction, default=None,
                    help="synchroniczny ocr/ocr zamiast ocr_async (--no-sync wymusza async)")
    ap.add_argument("--language", default=None, help="kod języka dla trybu sync, np. pl")
    ap.add_argument("-o", "--output-dir", dest="output_dir", default=None, help="folder wyjściowy")
    ap.add_argument("--poll-interval", dest="poll_interval_s", type=float, default=None,
                    help="sekundy między odpytaniami w trybie async")
    ap.add_argument("--poll-max-attempts", dest="poll_max_attempts", type=int, default=None,
                    help="maks. liczba odpytań w trybie async")
    args = ap.parse_args(argv)
    settings = resolve_settings(DEFAULTS, vars(args), args.config, DEFAULT_CONFIG_FILE,
                                path_keys=("file", "output_dir"))
    return argparse.Namespace(**settings)


def main() -> None:
    global OUT_DIR
    args = parse_args()
    OUT_DIR = Path(args.output_dir)

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
        text, raw = ocr_async(file_id, args.provider, headers, args.poll_interval_s, args.poll_max_attempts)

    OUT_DIR.mkdir(exist_ok=True)
    stem = src.stem.strip()
    (OUT_DIR / f"{stem}.ocr.txt").write_text(text, encoding="utf-8")
    (OUT_DIR / f"{stem}.ocr.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano: {OUT_DIR / (stem + '.ocr.txt')}\n")
    print(text[:3000] + ("\n..." if len(text) > 3000 else ""))


if __name__ == "__main__":
    main()
