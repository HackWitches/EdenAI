"""Krok 4: tekst z OCR -> JSON przez LLM - POST /v3/chat/completions  (ustawienia: config.json -> "llm")
(format zgodny z OpenAI Chat Completions; prompt systemowy w config_files/llm_prompt.txt)
"""
import json
import sys

import requests

from config import CFG, auth_headers, load_llm_prompt, parse_response


def text_to_json(text: str, model: str | None = None) -> dict:
    llm = CFG["llm"]
    payload = {
        "model": model or llm["model"],
        "messages": [
            {"role": "system", "content": load_llm_prompt()},
            {"role": "user", "content": text},
        ],
        "temperature": llm["temperature"],
    }
    response = requests.post(llm["url"], headers=auth_headers(), json=payload, timeout=llm["timeout_s"])
    result = parse_response(response)
    content = result["choices"][0]["message"]["content"].strip()

    # na wypadek gdyby model i tak owinął odpowiedź w ```json ... ```
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        sys.exit(f"LLM nie zwrócił poprawnego JSON ({e}):\n{content[:2000]}")
