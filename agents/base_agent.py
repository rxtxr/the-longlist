"""Together API base agent — all agents inherit from this."""
import time
import requests
from typing import Optional
from config import TOGETHER_API_KEY, TOGETHER_BASE_URL, MODELS, MAX_TOKENS


class BaseAgent:
    name: str = "base"
    model_key: str = "historiker"
    system_prompt: str = "Du bist ein hilfreicher, präziser Assistent."

    def __init__(self):
        self.model = MODELS[self.model_key]
        self._api_key = TOGETHER_API_KEY
        self._base_url = TOGETHER_BASE_URL

    def call(
        self,
        prompt: str,
        temperature: float = 0.5,
        max_tokens: Optional[int] = None,
        system_override: Optional[str] = None,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_override or self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens or MAX_TOKENS[self.model_key],
        }

        for attempt in range(3):
            try:
                resp = requests.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=180,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except requests.RequestException as e:
                print(f"  [{self.name}] API-Fehler (Versuch {attempt+1}/3): {e}")
                if attempt < 2:
                    time.sleep(2 ** (attempt + 1))
        return f"[FEHLER: {self.name} konnte keine Antwort abrufen]"
