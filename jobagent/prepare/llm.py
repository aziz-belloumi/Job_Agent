"""Thin Ollama HTTP wrapper used by cover_letter.py."""

from typing import Any

import requests


def call(prompt: str, cfg: dict[str, Any]) -> str:
    """Send prompt to the configured Ollama endpoint; return raw response text.

    Args:
        prompt: The full prompt string to send.
        cfg: Full cv.yaml config dict (cover_letter sub-key is read here).

    Returns:
        Raw text response from the model.

    Raises:
        requests.HTTPError: If the Ollama API returns a non-2xx status.
        requests.Timeout: If the request exceeds 120 seconds.
    """
    cl_cfg = cfg.get("cover_letter", {})
    url = cl_cfg.get("ollama_url", "http://127.0.0.1:11434") + "/api/generate"
    payload = {
        "model": cl_cfg.get("model", "qwen2.5:3b-instruct-q4_K_M"),
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": cl_cfg.get("temperature", 0.4),
            "num_predict": 512,
        },
    }
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    return r.json().get("response", "").strip()


def health_check(cfg: dict[str, Any]) -> bool:
    """Return True if Ollama is reachable and the configured model is available."""
    cl_cfg = cfg.get("cover_letter", {})
    url = cl_cfg.get("ollama_url", "http://127.0.0.1:11434") + "/api/tags"
    model = cl_cfg.get("model", "qwen2.5:3b-instruct-q4_K_M")
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        names = [m["name"] for m in r.json().get("models", [])]
        return model in names
    except Exception:
        return False
