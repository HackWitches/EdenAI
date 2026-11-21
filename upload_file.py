import os
import sys
from pathlib import Path

import requests


def load_api_key() -> str:
    key = os.environ.get("EDENAI_API_KEY")
    env_file = Path(__file__).parent / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("EDENAI_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit("Brak klucza: ustaw EDENAI_API_KEY w zmiennej środowiskowej lub w pliku .env")
    return key


url = "https://api.edenai.run/v3/upload"
headers = {
    # Eden AI wymaga prefiksu "Bearer " przed kluczem
    "Authorization": f"Bearer {load_api_key()}"
}

file_path = (
    "C:\\Hackathon2026\\Formularze-Wypakowane\\1. Wniosek o ustalenie numeru porządkowego nieruchomości"
    " - materiał referencyjny dla Uczestników do zadania\\Wniosek o ustalenie numeru porządkowego nieruchomości.docx"
)

data = {
    "purpose": "assistants"  # Optional: describe intended use
}

with open(file_path, "rb") as f:
    response = requests.post(url, headers=headers, files={"file": f}, data=data, timeout=120)

result = response.json()
if not response.ok or "file_id" not in result:
    sys.exit(f"Upload nie powiódł się (HTTP {response.status_code}): {result}")

print(f"File ID: {result['file_id']}")
print(f"Filename: {result['file_name']}")
print(f"Size: {result['file_size']} bytes")
print(f"Expires at: {result['expires_at']}")
