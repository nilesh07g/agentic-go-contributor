"""Verify GEMINI_API_KEY and GITHUB_TOKEN are valid before running the agent."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import requests
import google.generativeai as genai


def check_gemini() -> bool:
    key = os.environ.get("GEMINI_API_KEY")
    if not key or key == "your_gemini_key_here":
        print("[FAIL] GEMINI_API_KEY missing from .env")
        return False
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel(os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))
        r = model.generate_content("Reply with exactly: hello")
        print(f"[OK]   Gemini API: got reply {r.text.strip()!r}")
        return True
    except Exception as e:
        print(f"[FAIL] Gemini API: {e}")
        return False


def check_github() -> bool:
    token = os.environ.get("GITHUB_TOKEN")
    if not token or token == "your_github_token_here":
        print("[WARN] GITHUB_TOKEN missing — agent will work but with strict rate limits.")
        return True
    try:
        r = requests.get(
            "https://api.github.com/repos/spf13/cobra/issues/1",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        r.raise_for_status()
        print(f"[OK]   GitHub API: fetched issue {r.json().get('title')!r}")
        return True
    except Exception as e:
        print(f"[FAIL] GitHub API: {e}")
        return False


def main() -> int:
    ok = True
    ok &= check_gemini()
    ok &= check_github()
    if ok:
        print("\n[OK] All keys working. Ready to run agent.py.")
        return 0
    print("\n[FAIL] One or more keys did not work. See messages above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
