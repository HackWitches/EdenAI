"""Punkt startowy: pliki/foldery wejściowe -> JSON (wsadowo).

  1. convert.to_pdf              - .docx/.doc -> PDF (lokalnie, MS Word)
  2. upload_file / upload_files  - POST /v3/upload            -> file_id
  3. ocr.ocr_file                - POST /v3/universal-ai      -> tekst
  4. llm.text_to_json            - POST /v3/chat/completions  -> JSON

Struktura katalogów wejścia jest odtwarzana w output/, np.
  input_files/1. Wniosek .../Wniosek.docx  ->  output/input_files/1. Wniosek .../Wniosek.docx.json

Ustawienia (od najwyższego priorytetu):
  1. argumenty wiersza poleceń  (python main.py --help)
  2. plik konfiguracyjny JSON   (domyślnie config_files/settings.json, albo --config <plik>)
  3. wartości domyślne poniżej
Jeśli pliku konfiguracyjnego nie ma, używane są argumenty + wartości domyślne.
"""
import argparse
import json
import sys
from pathlib import Path

from config import BASE_DIR, CONFIG_DIR, OUTPUT_DIR
from convert import to_pdf
from llm import text_to_json
from ocr import ocr_file
from upload_file import upload_file, upload_files

# Pliki lub foldery do przetworzenia (foldery są przeszukiwane rekurencyjnie).
INPUT_PATHS = [
    BASE_DIR / "input_files",
]

# Rozszerzenia obsługiwane przez obecny proces (porównanie bez rozróżniania wielkości liter).
# Word -> konwersja do PDF; PDF i obrazy idą do OCR bez zmian.
INPUT_EXTENSIONS = [
    ".docx", ".doc", ".odt", ".rtf",
    ".pdf",
    ".png", ".jpg", ".jpeg",
]

DEFAULT_CONFIG_FILE = CONFIG_DIR / "settings.json"
DEFAULTS = {
    "input_paths": [str(p) for p in INPUT_PATHS],
    "extensions": INPUT_EXTENSIONS,
    "output_dir": str(OUTPUT_DIR),
    "ocr_provider": "mistral",
    "llm_model": "openai/gpt-4o",
}


def collect_files(input_paths, extensions, output_dir=OUTPUT_DIR) -> list[tuple[Path, Path]]:
    """Zwraca listę (plik_wejściowy, katalog_wyjściowy) z odtworzoną strukturą folderów."""
    exts = {e.lower() for e in extensions}
    found = []
    for entry in map(Path, input_paths):
        if not entry.exists():
            print(f"Pomijam, nie istnieje: {entry}")
            continue
        entry = entry.resolve()
        files = [entry] if entry.is_file() else sorted(p for p in entry.rglob("*") if p.is_file())
        for f in files:
            if f.suffix.lower() not in exts:
                continue
            # wewnątrz projektu: ścieżka względem projektu; poza nim: względem rodzica wpisu
            try:
                rel_dir = f.parent.relative_to(BASE_DIR.resolve())
            except ValueError:
                rel_dir = f.parent.relative_to(entry.parent)
            found.append((f, Path(output_dir) / rel_dir))
    # bez duplikatów, gdy ten sam plik jest podany i jako plik, i w folderze
    return list(dict.fromkeys(found))


def process(file_id: str, src: Path, out_dir: Path,
            ocr_provider: str = "mistral", llm_model: str = "openai/gpt-4o") -> Path:
    """OCR + LLM dla jednego pliku, zapis wyników w out_dir."""
    # nazwa z rozszerzeniem źródła, bo w jednym folderze są np. X.docx, X.pdf, X.jpg
    base = src.stem.strip() + src.suffix.lower()

    ocr_result = ocr_file(file_id, provider=ocr_provider)
    text = ocr_result["output"]["text"]
    (out_dir / f"{base}.ocr.txt").write_text(text, encoding="utf-8")
    print(f"      OCR: {len(text)} znaków")

    data = text_to_json(text, model=llm_model)
    out_file = out_dir / f"{base}.json"
    out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_file


def main(input_paths=INPUT_PATHS, extensions=INPUT_EXTENSIONS, output_dir=OUTPUT_DIR,
         ocr_provider="mistral", llm_model="openai/gpt-4o"):
    files = collect_files(input_paths, extensions, output_dir)
    if not files:
        sys.exit("Brak plików do przetworzenia (sprawdź input_paths i extensions)")
    print(f"Plików do przetworzenia: {len(files)}\n")

    print("[1/4] Konwersja do PDF...")
    ready = []  # (src, out_dir, plik_do_uploadu)
    for src, out_dir in files:
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            pdf = to_pdf(src, out_dir, out_name=f"{src.stem.strip()}{src.suffix.lower()}.pdf")
            ready.append((src, out_dir, pdf))
        except Exception as e:
            print(f"      konwersja nieudana: {src.name}: {e}")

    print(f"[2/4] Upload ({len(ready)} plików)...")
    if len(ready) == 1:
        uploads = [upload_file(ready[0][2])]
    else:
        uploads = upload_files([pdf for _, _, pdf in ready])

    print("[3/4 + 4/4] OCR i LLM -> JSON...")
    done, failed = [], []
    for (src, out_dir, _), uploaded in zip(ready, uploads):
        print(f"  - {src.parent.name}/{src.name}")
        if uploaded is None:
            failed.append(src)
            continue
        try:
            out_file = process(uploaded["file_id"], src, out_dir, ocr_provider, llm_model)
            print(f"      -> {out_file}")
            done.append(out_file)
        except (SystemExit, Exception) as e:
            print(f"      błąd: {e}")
            failed.append(src)

    failed += [src for src, _ in files if src not in {r[0] for r in ready}]
    print(f"\nGotowe: {len(done)} OK, {len(failed)} błędów. Wyniki w {output_dir}")
    for src in failed:
        print(f"  BŁĄD: {src}")
    return done


def load_config_file(path: Path) -> dict:
    """Wczytuje JSON z ustawieniami; ścieżki względne liczone od folderu projektu."""
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"Niepoprawny JSON w {path}: {e}")
    unknown = set(cfg) - set(DEFAULTS)
    if unknown:
        sys.exit(f"Nieznane klucze w {path}: {sorted(unknown)} (dozwolone: {sorted(DEFAULTS)})")
    base = BASE_DIR
    if "input_paths" in cfg:
        cfg["input_paths"] = [str(base / p) for p in cfg["input_paths"]]
    if "output_dir" in cfg:
        cfg["output_dir"] = str(base / cfg["output_dir"])
    return cfg


def parse_args(argv=None) -> dict:
    ap = argparse.ArgumentParser(description="Pliki/foldery -> PDF -> upload -> OCR -> LLM -> JSON (Eden AI)")
    ap.add_argument("input_paths", nargs="*", metavar="PATH",
                    help="pliki lub foldery do przetworzenia (foldery rekurencyjnie)")
    ap.add_argument("-c", "--config", type=Path, default=None,
                    help="plik konfiguracyjny JSON (domyślnie config_files/settings.json, jeśli istnieje)")
    ap.add_argument("-e", "--extensions", nargs="+", metavar="EXT",
                    help="rozszerzenia plików, np. .pdf .docx")
    ap.add_argument("-o", "--output-dir", dest="output_dir", help="folder wyjściowy")
    ap.add_argument("--ocr-provider", dest="ocr_provider", help="np. mistral, amazon, google, microsoft")
    ap.add_argument("--llm-model", dest="llm_model", help="np. openai/gpt-4o")
    args = ap.parse_args(argv)

    settings = dict(DEFAULTS)

    config_path = args.config or DEFAULT_CONFIG_FILE
    if config_path.exists():
        print(f"Konfiguracja: {config_path}")
        settings.update(load_config_file(config_path))
    elif args.config:  # podany wprost, a nie istnieje -> błąd
        sys.exit(f"Plik konfiguracyjny nie istnieje: {args.config}")
    else:
        print("Brak pliku konfiguracyjnego - używam argumentów i wartości domyślnych")

    # argumenty podane wprost nadpisują plik konfiguracyjny
    cli = {k: v for k, v in vars(args).items() if k != "config" and v not in (None, [])}
    if "extensions" in cli:
        cli["extensions"] = [e if e.startswith(".") else f".{e}" for e in cli["extensions"]]
    settings.update(cli)
    return settings


if __name__ == "__main__":
    main(**parse_args())
