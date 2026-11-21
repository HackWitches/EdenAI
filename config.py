"""Wspólna konfiguracja: klucz API, adresy endpointów, nagłówki."""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
CONFIG_DIR = BASE_DIR / "config_files"  # .env, settings.json

UPLOAD_URL = "https://api.edenai.run/v3/upload"
OCR_URL = "https://api.edenai.run/v3/universal-ai"
LLM_URL = "https://api.edenai.run/v3/chat/completions"


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
