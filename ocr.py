"""Krok 3: OCR - POST /v3/universal-ai  (ustawienia: config.json -> "ocr")

  mode "sync":  POST <url>        {"model": "ocr/ocr/<provider>", "input": {"file": file_id}}  -> output.text
  mode "async": POST <async_url>  {"model": "ocr/ocr_async/<provider>", ...}  -> job_id
                GET  <async_url>/<job_id> aż status == success              -> output.raw_text
"""
import json
import sys
import time

import requests

from config import CFG, auth_headers, parse_response


def ocr_file(file_id: str, provider: str | None = None, language: str | None = None) -> dict:
    """OCR synchroniczny; zwraca pełną odpowiedź, tekst jest w ["output"]["text"]."""
    oc = CFG["ocr"]
    body = {"model": f"ocr/ocr/{provider or oc['provider']}", "input": {"file": file_id}}
    if language or oc["language"]:
        body["input"]["language"] = language or oc["language"]
    response = requests.post(oc["url"], headers=auth_headers(), json=body, timeout=oc["timeout_s"])
    result = parse_response(response)
    if result.get("status") != "success":
        sys.exit(f"OCR nie powiódł się: {result}")
    return result


def ocr_file_async(file_id: str, provider: str | None = None) -> dict:
    """OCR asynchroniczny (zadanie + odpytywanie); zwraca odpowiedź, tekst w ["output"]["raw_text"]."""
    oc = CFG["ocr"]
    headers = auth_headers()
    body = {"model": f"ocr/ocr_async/{provider or oc['provider']}", "input": {"file": file_id}}
    job = parse_response(requests.post(oc["async_url"], headers=headers, json=body, timeout=oc["timeout_s"]))
    job_id = job.get("public_id") or job.get("id") or job.get("job_id")
    if not job_id:
        sys.exit(f"Brak job_id w odpowiedzi: {json.dumps(job, ensure_ascii=False, indent=2)}")
    print(f"      job_id = {job_id}, czekam na wynik", end="", flush=True)
    for _ in range(oc["poll_max_attempts"]):
        data = parse_response(requests.get(f"{oc['async_url']}/{job_id}", headers=headers,
                                           timeout=oc["poll_timeout_s"]))
        status = data.get("status")
        if status == "success":
            print(" gotowe")
            return data
        if status == "fail":
            print()
            sys.exit(f"OCR nie powiódł się: {json.dumps(data, ensure_ascii=False, indent=2)}")
        print(".", end="", flush=True)
        time.sleep(oc["poll_interval_s"])
    sys.exit("\nPrzekroczono czas oczekiwania na wynik OCR")


def run_ocr(file_id: str) -> tuple[str, dict]:
    """OCR wg ustawień (ocr.mode). Zwraca (tekst, pełna_odpowiedź)."""
    if CFG["ocr"]["mode"] == "async":
        raw = ocr_file_async(file_id)
        out = raw.get("output") or {}
        return out.get("raw_text") or out.get("text", ""), raw
    raw = ocr_file(file_id)
    return raw["output"].get("text", ""), raw
