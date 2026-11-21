"""Punkt startowy: pliki/foldery wejściowe -> PDF -> upload -> OCR -> LLM -> JSON (wsadowo).

  1. convert.to_pdf              - .docx/.doc -> PDF (lokalnie, MS Word)
  2. upload_file / upload_files  - POST /v3/upload
  3. ocr.run_ocr                 - POST /v3/universal-ai  (sync lub async, wg ocr.mode)
  4. llm.text_to_json            - POST /v3/chat/completions

Ustawienia: config_files/config.json (opis w config.py), argumenty: python main.py --help
Wyniki: output/<ta sama ścieżka co wejście>/<plik>.<rozszerzenie>.ocr.txt i .json
"""
import json
import sys

from config import CFG, parse_cli
from inputs import collect_files, convert_and_upload, output_base, print_summary
from llm import text_to_json
from ocr import run_ocr


def main(argv=None):
    parse_cli("Pliki/foldery -> PDF -> upload -> OCR -> LLM -> JSON (Eden AI)", argv=argv)
    files = collect_files()
    if not files:
        sys.exit("Brak plików do przetworzenia (sprawdź input.paths i input.extensions)")
    print(f"Plików: {len(files)} | OCR: {CFG['ocr']['provider']} ({CFG['ocr']['mode']}) "
          f"| LLM: {CFG['llm']['model']}\n")

    prepared = convert_and_upload(files)

    print("[3+4] OCR i LLM -> JSON...")
    done, failed = [], []
    for src, out_dir, uploaded in prepared:
        print(f"  - {src.parent.name}/{src.name}")
        if uploaded is None:
            failed.append(src)
            continue
        try:
            base = output_base(src)
            text, _ = run_ocr(uploaded["file_id"])
            (out_dir / f"{base}.ocr.txt").write_text(text, encoding="utf-8")
            print(f"      OCR: {len(text)} znaków")

            data = text_to_json(text)
            out_file = out_dir / f"{base}.json"
            out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"      -> {out_file}")
            done.append(out_file)
        except (SystemExit, Exception) as e:
            print(f"      błąd: {e}")
            failed.append(src)

    print_summary(done, failed)
    return done


if __name__ == "__main__":
    main()
