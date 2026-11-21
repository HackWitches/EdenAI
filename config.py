"""Konfiguracja projektu.

Pliki w config_files/:
  config.json      - WSZYSTKIE ustawienia, pogrupowane wg etapów procesu:
                       input  -> skąd brać pliki i gdzie zapisywać wyniki
                       upload -> POST /v3/upload
                       ocr    -> wybór dostawcy OCR + tryb + parametry  (POST /v3/universal-ai)
                       llm    -> wybór modelu LLM + parametry           (POST /v3/chat/completions)
  .env             - sekret: EDENAI_API_KEY (osobno, bo nie trafia do gita)
  llm_prompt.txt   - prompt systemowy LLM (osobno, bo to długi tekst wielowierszowy)

Pierwszeństwo: argumenty wiersza poleceń > config.json (lub --config <plik>) > DEFAULTS poniżej.
Klucze zaczynające się od "_" w config.json to komentarze i są pomijane.
"""
import argparse
import copy
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config_files"
DEFAULT_CONFIG_FILE = CONFIG_DIR / "config.json"
ENV_FILE = CONFIG_DIR / ".env"

# Jedyne miejsce z wartościami domyślnymi w kodzie; config.json ma identyczną strukturę.
DEFAULTS = {
    "input": {
        "paths": ["input_files"],  # pliki lub foldery (foldery rekurencyjnie), względem projektu
        "extensions": [".docx", ".doc", ".odt", ".rtf", ".pdf", ".png", ".jpg", ".jpeg"],
        "output_dir": "output",
    },
    "upload": {
        "url": "https://api.edenai.run/v3/upload",
        "purpose": "ocr",
        "timeout_s": 120,
    },
    "ocr": {
        "provider": "mistral",  # model Eden AI: ocr/ocr/<provider> lub ocr/ocr_async/<provider>
        "mode": "sync",         # "sync" (ocr/ocr) albo "async" (ocr/ocr_async, z odpytywaniem)
        "language": None,       # np. "pl"; None = autodetekcja dostawcy
        "url": "https://api.edenai.run/v3/universal-ai",
        "async_url": "https://api.edenai.run/v3/universal-ai/async",
        "timeout_s": 300,       # zapytanie sync oraz utworzenie zadania async
        "poll_interval_s": 3,
        "poll_max_attempts": 120,
        "poll_timeout_s": 60,
    },
    "llm": {
        "model": "openai/gpt-4o",  # <dostawca>/<model> w Eden AI
        "temperature": 0,
        "prompt_file": "config_files/llm_prompt.txt",
        "url": "https://api.edenai.run/v3/chat/completions",
        "timeout_s": 300,
    },
}

# Aktualne ustawienia. Moduły czytają CFG w chwili wywołania, więc argumenty CLI
# zastosowane w parse_cli() działają wszędzie.
CFG: dict = {}


def project_path(p: str | Path) -> Path:
    """Ścieżka względna z konfiguracji -> względem folderu projektu."""
    return BASE_DIR / p


def load_config(path: Path | None = None, verbose: bool = False) -> dict:
    """Wczytuje DEFAULTS + plik JSON do CFG. path=None -> config.json, jeśli istnieje."""
    cfg = copy.deepcopy(DEFAULTS)
    file = path or DEFAULT_CONFIG_FILE
    if file.exists():
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"Niepoprawny JSON w {file}: {e}")
        for section, values in data.items():
            if section.startswith("_"):
                continue
            if section not in cfg:
                sys.exit(f"Nieznana sekcja '{section}' w {file} (dozwolone: {sorted(cfg)})")
            for key, value in values.items():
                if key.startswith("_"):
                    continue
                if key not in cfg[section]:
                    sys.exit(f"Nieznany klucz '{section}.{key}' w {file} "
                             f"(dozwolone: {sorted(cfg[section])})")
                cfg[section][key] = value
        if verbose:
            print(f"Konfiguracja: {file}")
    elif path:  # podany wprost, a nie istnieje -> błąd
        sys.exit(f"Plik konfiguracyjny nie istnieje: {path}")
    elif verbose:
        print("Brak config_files/config.json - używam argumentów i wartości domyślnych")
    CFG.clear()
    CFG.update(cfg)
    return CFG


def parse_cli(description: str, with_llm: bool = True, argv=None) -> dict:
    """Wspólne argumenty dla main.py i ocr_app.py; wczytuje config i nakłada na niego argumenty."""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("paths", nargs="*", metavar="PATH",
                    help="pliki lub foldery do przetworzenia (zastępują input.paths)")
    ap.add_argument("-c", "--config", type=Path, default=None,
                    help="plik ustawień (domyślnie config_files/config.json, jeśli istnieje)")
    g = ap.add_argument_group("input")
    g.add_argument("-e", "--extensions", nargs="+", metavar="EXT", help="np. .pdf .docx (kropka opcjonalna)")
    g.add_argument("-o", "--output-dir", help="folder wyjściowy")
    g = ap.add_argument_group("ocr")
    g.add_argument("--ocr-provider", help="np. mistral, amazon, google, microsoft")
    g.add_argument("--ocr-mode", choices=["sync", "async"])
    g.add_argument("--ocr-language", help="np. pl")
    g.add_argument("--ocr-poll-interval", type=float, metavar="S", help="sekundy między odpytaniami (async)")
    g.add_argument("--ocr-poll-max-attempts", type=int, metavar="N", help="maks. liczba odpytań (async)")
    if with_llm:
        g = ap.add_argument_group("llm")
        g.add_argument("--llm-model", help="np. openai/gpt-4o")
        g.add_argument("--llm-temperature", type=float)
    a = ap.parse_args(argv)

    cfg = load_config(a.config, verbose=True)
    overrides = {
        ("input", "paths"): [str(Path(p).resolve()) for p in a.paths] or None,
        ("input", "extensions"): [e if e.startswith(".") else f".{e}" for e in a.extensions or []] or None,
        ("input", "output_dir"): str(Path(a.output_dir).resolve()) if a.output_dir else None,
        ("ocr", "provider"): a.ocr_provider,
        ("ocr", "mode"): a.ocr_mode,
        ("ocr", "language"): a.ocr_language,
        ("ocr", "poll_interval_s"): a.ocr_poll_interval,
        ("ocr", "poll_max_attempts"): a.ocr_poll_max_attempts,
        ("llm", "model"): getattr(a, "llm_model", None),
        ("llm", "temperature"): getattr(a, "llm_temperature", None),
    }
    for (section, key), value in overrides.items():
        if value is not None:
            cfg[section][key] = value
    return cfg


def load_api_key() -> str:
    """Czyta klucz z EDENAI_API_KEY albo z pliku config_files/.env."""
    key = os.environ.get("EDENAI_API_KEY")
    if not key and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("EDENAI_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit("Brak klucza: ustaw EDENAI_API_KEY w zmiennej środowiskowej lub w pliku config_files/.env")
    return key


def auth_headers() -> dict:
    # Eden AI wymaga prefiksu "Bearer " przed kluczem
    return {"Authorization": f"Bearer {load_api_key()}"}


def parse_response(response) -> dict:
    """Zwraca JSON odpowiedzi albo kończy program z czytelnym błędem."""
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text}
    if not response.ok:
        sys.exit(f"Błąd HTTP {response.status_code} z {response.url}: {data}")
    return data


def load_llm_prompt() -> str:
    """Prompt systemowy LLM z pliku llm.prompt_file."""
    path = project_path(CFG["llm"]["prompt_file"])
    if not path.exists():
        sys.exit(f"Brak pliku z promptem LLM: {path}")
    return path.read_text(encoding="utf-8").strip()


load_config()  # domyślne ustawienia już przy imporcie (moduły działają też bez parse_cli)
