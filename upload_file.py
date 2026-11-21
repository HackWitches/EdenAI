"""Krok 2: upload pliku - POST https://api.edenai.run/v3/upload"""
import sys
from pathlib import Path

import requests

from config import UPLOAD_URL, auth_headers, parse_response


def upload_file(file_path: str | Path, purpose: str = "ocr") -> dict:
    """Wysyła plik do Eden AI i zwraca odpowiedź (file_id, file_name, file_size, expires_at...)."""
    with open(file_path, "rb") as f:
        response = requests.post(UPLOAD_URL, headers=auth_headers(), files={"file": f},
                                 data={"purpose": purpose}, timeout=120)
    result = parse_response(response)
    if "file_id" not in result:
        sys.exit(f"Brak file_id w odpowiedzi uploadu: {result}")
    return result
