import requests

url = "https://api.edenai.run/v3/chat/completions"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}

payload = {
    "model": "openai/gpt-latest",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Summarize this document."},
                {"type": "file", "file": {"file_id": "550e8400-e29b-41d4-a716-446655440000"}}
            ]
        }
    ]
}

response = requests.post(url, headers=headers, json=payload)
result = response.json()
print(result["choices"][0]["message"]["content"])