"""Krok 2: upload pliku - POST /v3/upload  (ustawienia: config.json -> "upload")"""
import sys
from pathlib import Path

import requests

from config import CFG, auth_headers, parse_response


def upload_file(file_path: str | Path, purpose: str | None = None) -> dict:
    """Wysyła plik do Eden AI i zwraca odpowiedź (file_id, file_name, file_size, expires_at...)."""
    up = CFG["upload"]
    with open(file_path, "rb") as f:
        response = requests.post(up["url"], headers=auth_headers(), files={"file": f},
                                 data={"purpose": purpose or up["purpose"]}, timeout=up["timeout_s"])
    result = parse_response(response)
    if "file_id" not in result:
        sys.exit(f"Brak file_id w odpowiedzi uploadu: {result}")
    return result


def upload_files(file_paths: list[str | Path], purpose: str | None = None) -> list[dict | None]:
    """Upload wielu plików wg sekcji "Upload Multiple Files" z dokumentacji Eden AI.

    Eden AI nie ma osobnego endpointu batch: dokumentacja wysyła każdy plik osobnym
    POST /v3/upload. Zwraca listę odpowiedzi w tej samej kolejności co file_paths;
    None oznacza, że upload tego pliku się nie powiódł (reszta leci dalej).
    """
    results = []
    for path in file_paths:
        try:
            results.append(upload_file(path, purpose))
        except SystemExit as e:
            print(f"      upload nieudany: {Path(path).name}: {e}")
            results.append(None)
    return results
