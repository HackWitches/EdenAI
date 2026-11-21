"""Sam OCR (bez LLM): pliki/foldery wejściowe -> PDF -> upload -> OCR (wsadowo).

Te same pliki wejściowe i te same ustawienia OCR co main.py (config_files/config.json).
Zapisuje surową odpowiedź OCR (.ocr.json) obok tekstu (.ocr.txt).
Argumenty: python ocr_app.py --help
"""
import json
import sys

from config import CFG, parse_cli
from inputs import collect_files, convert_and_upload, output_base, print_summary
from ocr import run_ocr


def main(argv=None) -> None:
    parse_cli("OCR plików przez Eden AI (bez LLM)", with_llm=False, argv=argv)
    files = collect_files()
    if not files:
        sys.exit("Brak plików do przetworzenia (sprawdź input.paths i input.extensions)")
    print(f"Plików: {len(files)} | OCR: {CFG['ocr']['provider']} ({CFG['ocr']['mode']})\n")

    prepared = convert_and_upload(files)

    print("[3] OCR...")
    done, failed = [], []
    for src, out_dir, uploaded in prepared:
        print(f"  - {src.parent.name}/{src.name}")
        if uploaded is None:
            failed.append(src)
            continue
        try:
            base = output_base(src)
            text, raw = run_ocr(uploaded["file_id"])
            out_file = out_dir / f"{base}.ocr.txt"
            out_file.write_text(text, encoding="utf-8")
            (out_dir / f"{base}.ocr.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2),
                                                      encoding="utf-8")
            print(f"      {len(text)} znaków -> {out_file}")
            done.append(out_file)
        except (SystemExit, Exception) as e:
            print(f"      błąd: {e}")
            failed.append(src)

    print_summary(done, failed)


if __name__ == "__main__":
    main()
