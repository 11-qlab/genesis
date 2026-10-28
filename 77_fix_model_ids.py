#!/usr/bin/env python3
"""Patch 76_: replace retired model IDs with current ones."""
from pathlib import Path
p = Path(__file__).resolve().parent / "76_multi_model_differential.py"
s = p.read_text()

# Groq: llama-3.1-8b-instant retired 2026-08-16 -> openai/gpt-oss-20b
s = s.replace('"model": "llama-3.1-8b-instant"', '"model": "openai/gpt-oss-20b"')
# Groq: llama-3.3-70b-versatile retired 2026-08-16 -> qwen/qwen3.8-27b (cross-family)
s = s.replace('"model": "llama-3.3-70b-versatile"', '"model": "qwen/qwen3.8-27b"')
# Gemini: gemini-2.0-flash shut down 2026-06-01 -> gemini-2.5-flash
s = s.replace('"model": "gemini-2.0-flash"', '"model": "gemini-2.5-flash"')
# Rename labels to reflect actual models
s = s.replace('"groq_llama8b"', '"groq_oss20b"')
s = s.replace('"groq_llama70b"', '"groq_qwen27b"')

p.write_text(s)
print("patched 76_: Groq -> gpt-oss-20b / qwen3.8-27b; Gemini -> 2.5-flash")
