"""Wspólna konfiguracja: klucz API, adresy endpointów, nagłówki, ładowanie ustawień."""
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
CONFIG_DIR = BASE_DIR / "config_files"  # .env, settings.json, ocr_app.json, api.json, llm_prompt.txt

# Ustawienia API: wartości domyślne, nadpisywane przez config_files/api.json (jeśli istnieje).
API_CONFIG_FILE = CONFIG_DIR / "api.json"
API_DEFAULTS = {
    "upload_url": "https://api.edenai.run/v3/upload",
    "ocr_url": "https://api.edenai.run/v3/universal-ai",
    "ocr_async_url": "https://api.edenai.run/v3/universal-ai/async",
    "llm_url": "https://api.edenai.run/v3/chat/completions",
    "upload_purpose": "ocr",
    "upload_timeout_s": 120,
    "ocr_timeout_s": 300,
    "ocr_async_create_timeout_s": 120,
    "ocr_async_poll_timeout_s": 60,
    "llm_timeout_s": 300,
    "llm_temperature": 0,
    "llm_prompt_file": "config_files/llm_prompt.txt",
}


def _load_api_config() -> dict:
    cfg = dict(API_DEFAULTS)
    if API_CONFIG_FILE.exists():
        try:
            data = json.loads(API_CONFIG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"Niepoprawny JSON w {API_CONFIG_FILE}: {e}")
        unknown = set(data) - set(API_DEFAULTS)
        if unknown:
            sys.exit(f"Nieznane klucze w {API_CONFIG_FILE}: {sorted(unknown)} (dozwolone: {sorted(API_DEFAULTS)})")
        cfg.update(data)
    return cfg


API = _load_api_config()
UPLOAD_URL = API["upload_url"]
OCR_URL = API["ocr_url"]
OCR_ASYNC_URL = API["ocr_async_url"]
LLM_URL = API["llm_url"]


def load_llm_prompt() -> str:
    """Czyta prompt systemowy LLM z pliku wskazanego w api.json (ścieżka względem projektu)."""
    path = BASE_DIR / API["llm_prompt_file"]
    if not path.exists():
        sys.exit(f"Brak pliku z promptem LLM: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_api_key() -> str:
    """Czyta klucz z EDENAI_API_KEY albo z pliku config_files/.env."""
    key = os.environ.get("EDENAI_API_KEY")
    env_file = CONFIG_DIR / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
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


def resolve_settings(defaults: dict, cli: dict, config_path: Path | None, default_config: Path,
                     path_keys: tuple = (), path_list_keys: tuple = ()) -> dict:
    """Łączy ustawienia: argumenty CLI > plik konfiguracyjny JSON > wartości domyślne.

    - config_path: plik z --config (musi istnieć) albo None -> default_config (opcjonalny).
    - cli: argumenty argparse; None / [] oznacza "nie podano" i nie nadpisuje.
    - path_keys / path_list_keys: klucze ze ścieżkami; ścieżki względne z pliku
      konfiguracyjnego są liczone od folderu projektu.
    """
    settings = dict(defaults)

    path = config_path or default_config
    if path.exists():
        print(f"Konfiguracja: {path}")
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"Niepoprawny JSON w {path}: {e}")
        unknown = set(cfg) - set(defaults)
        if unknown:
            sys.exit(f"Nieznane klucze w {path}: {sorted(unknown)} (dozwolone: {sorted(defaults)})")
        for k in path_keys:
            if cfg.get(k):
                cfg[k] = str(BASE_DIR / cfg[k])
        for k in path_list_keys:
            if k in cfg:
                cfg[k] = [str(BASE_DIR / p) for p in cfg[k]]
        settings.update(cfg)
    elif config_path:  # podany wprost, a nie istnieje -> błąd
        sys.exit(f"Plik konfiguracyjny nie istnieje: {config_path}")
    else:
        print("Brak pliku konfiguracyjnego - używam argumentów i wartości domyślnych")

    settings.update({k: v for k, v in cli.items() if k in defaults and v not in (None, [])})
    return settings
