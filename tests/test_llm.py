import json
from datetime import date
from types import SimpleNamespace as N

import anthropic
import httpx2 as httpx

from nopanic import llm


def _resp(obj, wrap=""):
    return N(content=[N(type="text", text=wrap + json.dumps(obj, ensure_ascii=False) + wrap)],
             usage=N(input_tokens=7, output_tokens=3))


ANSWER = {"sender": "CAF", "explanation": "📨 CAF", "original_text": "Bonjour", "deadline": "2026-12-15",
          "deadline_what": "envoyer", "needs_lawyer": False}


async def test_structured_output_path(monkeypatch):
    monkeypatch.setattr(llm, "_structured_ok", None)
    l = llm.LLM("k", "m", "c")
    calls = []

    async def create(**kw):
        calls.append(kw)
        return _resp(ANSWER)
    l.client.messages.create = create
    r = await l.analyze([llm.Attachment(b"x", "image/jpeg")], "uk", date(2026, 11, 22), None)
    assert r.deadline == date(2026, 12, 15) and r.sender == "CAF"
    assert "output_config" in calls[0]


async def test_fallback_when_structured_refused(monkeypatch):
    monkeypatch.setattr(llm, "_structured_ok", None)
    l = llm.LLM("k", "m", "c")
    calls = []

    async def create(**kw):
        calls.append(kw)
        if "output_config" in kw:
            raise anthropic.BadRequestError(
                "not supported", response=httpx.Response(400, request=httpx.Request("POST", "https://x")), body=None)
        return _resp(ANSWER, wrap="\n")
    l.client.messages.create = create
    r = await l.analyze([llm.Attachment(b"x", "image/jpeg")], "ru", date(2026, 11, 22), "note")
    assert r.explanation == "📨 CAF"
    assert "output_config" not in calls[-1] and "JSON schema" in calls[-1]["system"]
    assert llm._structured_ok is False
