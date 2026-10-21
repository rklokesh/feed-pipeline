#!/usr/bin/env python3
"""Diagnose the free AI providers: which Gemini models this key can use, and one tiny test call each."""
import json
import os

import requests

key = os.environ.get("GEMINI_API_KEY", "")
print("GEMINI_API_KEY present:", bool(key))
if key:
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": key, "pageSize": 200}, timeout=30)
    print("list models:", r.status_code)
    names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])] if r.ok else []
    flash = [n for n in names if "flash" in n]
    print("flash models:", ", ".join(flash[:25]))
    for model in (["gemini-flash-latest", "gemini-flash-lite-latest"] + flash[:4]):
        r = requests.post("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                          headers={"Authorization": f"Bearer {key}"}, timeout=60,
                          json={"model": model, "messages": [{"role": "user", "content": "Reply with {\"ok\": true}"}],
                                "response_format": {"type": "json_object"}})
        print(f"  {model}: {r.status_code} {r.text[:220]!r}")
tok = os.environ.get("GITHUB_TOKEN")
if tok:
    r = requests.post("https://models.github.ai/inference/chat/completions", timeout=60,
                      headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"},
                      json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Say ok"}]})
    print("github-models:", r.status_code, repr(r.text[:220]), dict(list(r.headers.items())[:6]))
