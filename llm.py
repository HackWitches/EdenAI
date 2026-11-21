"""Krok 4: tekst z OCR -> JSON przez LLM - POST https://api.edenai.run/v3/chat/completions
(format zgodny z OpenAI Chat Completions)
"""
import json
import sys

import requests

from config import API, LLM_URL, auth_headers, load_llm_prompt, parse_response

# Prompt systemowy: config_files/llm_prompt.txt (ścieżka ustawiana w config_files/api.json)


def text_to_json(text: str, model: str = "openai/gpt-4o") -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": load_llm_prompt()},
            {"role": "user", "content": text},
        ],
        "temperature": API["llm_temperature"],
    }
    response = requests.post(LLM_URL, headers=auth_headers(), json=payload, timeout=API["llm_timeout_s"])
    result = parse_response(response)
    content = result["choices"][0]["message"]["content"].strip()

    # na wypadek gdyby model i tak owinął odpowiedź w ```json ... ```
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        sys.exit(f"LLM nie zwrócił poprawnego JSON ({e}):\n{content[:2000]}")
