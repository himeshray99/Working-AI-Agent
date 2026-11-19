import json
import requests
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT

class OllamaClient:
    """Ollama client with a one-time health check to avoid per-row long timeouts."""
    def __init__(self, model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, timeout=OLLAMA_TIMEOUT):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._checked = False
        self._available = False
        self._unavailable_reason = "Ollama has not been checked"

    def _check(self):
        if self._checked:
            return
        self._checked = True
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            response.raise_for_status()
            models = response.json().get("models", [])
            names = {str(item.get("name", "")) for item in models}
            if self.model not in names and not any(name.startswith(self.model.split(":")[0] + ":") for name in names):
                self._unavailable_reason = f"Model '{self.model}' is not installed. Run: ollama pull {self.model}"
                return
            self._available = True
        except Exception as exc:
            self._unavailable_reason = f"Ollama is not reachable at {self.base_url}: {type(exc).__name__}"

    def chat_json(self, prompt: str) -> dict:
        self._check()
        if not self._available:
            raise RuntimeError(self._unavailable_reason)
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2}
            },
            timeout=self.timeout
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Ollama response was not a JSON object")
        return parsed
