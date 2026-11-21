"""Krok 2: upload pliku - POST https://api.edenai.run/v3/upload"""
import sys
from pathlib import Path

import requests

from config import API, UPLOAD_URL, auth_headers, parse_response


def upload_file(file_path: str | Path, purpose: str | None = None) -> dict:
    """Wysyła plik do Eden AI i zwraca odpowiedź (file_id, file_name, file_size, expires_at...).
    purpose=None -> wartość "upload_purpose" z config_files/api.json."""
    with open(file_path, "rb") as f:
        response = requests.post(UPLOAD_URL, headers=auth_headers(), files={"file": f},
                                 data={"purpose": purpose or API["upload_purpose"]},
                                 timeout=API["upload_timeout_s"])
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
