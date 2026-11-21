"""Krok 4: tekst z OCR -> JSON przez LLM - POST https://api.edenai.run/v3/chat/completions
(format zgodny z OpenAI Chat Completions)
"""
import json
import sys

import requests

from config import LLM_URL, auth_headers, parse_response

SYSTEM_PROMPT = """Jesteś parserem formularzy urzędowych.
Dostajesz tekst z OCR polskiego formularza (wniosku). Zamień go na ustrukturyzowany JSON:
{
  "tytul": "<tytuł formularza>",
  "sekcje": [
    {
      "nazwa": "<nazwa sekcji>",
      "pola": [
        {
          "etykieta": "<etykieta pola>",
          "typ": "text | radio | checkbox | select | date | number | textarea | file",
          "wartosc": "<wartość wpisana w formularzu albo null>",
          "opcje": ["<dla radio/checkbox/select>"],
          "wymagane": true | false | null,
          "podpowiedz": "<placeholder/opis albo null>"
        }
      ]
    }
  ],
  "reguly_dynamiczne": ["<opisy warunków typu: jeśli wybrano X, pokaż sekcje Y>"]
}
Zachowaj polskie znaki. Nie wymyślaj pól, których nie ma w tekście.
Zwróć WYŁĄCZNIE poprawny JSON, bez komentarzy i bez bloków ```."""


def text_to_json(text: str, model: str = "openai/gpt-4o") -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
    }
    response = requests.post(LLM_URL, headers=auth_headers(), json=payload, timeout=300)
    result = parse_response(response)
    content = result["choices"][0]["message"]["content"].strip()

    # na wypadek gdyby model i tak owinął odpowiedź w ```json ... ```
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        sys.exit(f"LLM nie zwrócił poprawnego JSON ({e}):\n{content[:2000]}")
