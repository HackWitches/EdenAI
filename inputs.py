"""Pliki wejściowe i wspólne kroki przygotowania (ustawienia: config.json -> "input").

Struktura katalogów wejścia jest odtwarzana w output_dir, np.
  input_files/1. Wniosek .../Wniosek.docx  ->  output/input_files/1. Wniosek .../Wniosek.docx.*
"""
from pathlib import Path

from config import BASE_DIR, CFG, project_path
from convert import to_pdf
from upload_file import upload_file, upload_files


def collect_files() -> list[tuple[Path, Path]]:
    """Zwraca listę (plik_wejściowy, katalog_wyjściowy) wg input.paths / extensions / output_dir."""
    inp = CFG["input"]
    exts = {e.lower() for e in inp["extensions"]}
    output_dir = project_path(inp["output_dir"])
    found = []
    for entry in map(project_path, inp["paths"]):
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
            found.append((f, output_dir / rel_dir))
    # bez duplikatów, gdy ten sam plik jest podany i jako plik, i w folderze
    return list(dict.fromkeys(found))


def output_base(src: Path) -> str:
    """Nazwa bazowa plików wynikowych - z rozszerzeniem źródła, bo w jednym folderze
    są np. X.docx, X.pdf, X.jpg."""
    return src.stem.strip() + src.suffix.lower()


def convert_and_upload(files: list[tuple[Path, Path]]) -> list[tuple[Path, Path, dict | None]]:
    """Kroki 1-2 dla wszystkich plików: konwersja do PDF + upload.
    Zwraca (src, out_dir, odpowiedź_uploadu | None przy błędzie) dla każdego pliku."""
    print("[1] Konwersja do PDF...")
    ready, results = [], {}
    for src, out_dir in files:
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            ready.append((src, out_dir, to_pdf(src, out_dir, out_name=f"{output_base(src)}.pdf")))
        except Exception as e:
            print(f"      konwersja nieudana: {src.name}: {e}")

    print(f"[2] Upload ({len(ready)} plików)...")
    uploads = [upload_file(ready[0][2])] if len(ready) == 1 else upload_files([p for _, _, p in ready])
    for (src, _, _), uploaded in zip(ready, uploads):
        results[src] = uploaded
    return [(src, out_dir, results.get(src)) for src, out_dir in files]


def print_summary(done: list, failed: list) -> None:
    print(f"\nGotowe: {len(done)} OK, {len(failed)} błędów. Wyniki w {project_path(CFG['input']['output_dir'])}")
    for src in failed:
        print(f"  BŁĄD: {src}")
