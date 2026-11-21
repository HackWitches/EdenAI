"""Krok 3: OCR - POST https://api.edenai.run/v3/universal-ai

Body: {"model": "ocr/ocr/<provider>", "input": {"file": "<file_id>"}}
Tekst wynikowy jest w output.text.
"""
import sys

import requests

from config import OCR_URL, auth_headers, parse_response


def ocr_file(file_id: str, provider: str = "mistral", language: str | None = None) -> dict:
    """Zwraca pełną odpowiedź OCR; tekst jest w ["output"]["text"]."""
    body = {"model": f"ocr/ocr/{provider}", "input": {"file": file_id}}
    if language:
        body["input"]["language"] = language
    response = requests.post(OCR_URL, headers=auth_headers(), json=body, timeout=300)
    result = parse_response(response)
    if result.get("status") != "success":
        sys.exit(f"OCR nie powiódł się: {result}")
    return result
