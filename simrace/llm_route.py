"""One model-call route for every local SN15 tool (C538 CREDITS, 2026-11-07).

Owner rule: no OpenRouter prepaid credit may move, fee included. Every local tool sends its chat bodies (OpenAI chat-completions
shape, the shape the agent writes) through `post_json()` / `send()` here instead of opening its own OpenRouter request.

Route (env SN15_LLM_ROUTE, default `auto`):
  auto        anthropic/* goes straight to api.anthropic.com when an Anthropic key is configured (ANTHROPIC_API_KEY in the env,
              ~/Documents/bittensor/sn15/.env, ~/.config/sn15/env or ~/sn15-ops/.env); without one it goes to OpenRouter pinned to
              provider Anthropic (BYOK) with the credit tripwire below.
  anthropic   direct only: no Anthropic key -> refuse (nothing is sent to OpenRouter).
  openrouter  explicit opt-in to the OpenRouter hop (BYOK pin + tripwire) even when an Anthropic key exists.
Non-Anthropic models (the pack's live labeler models, flash) always bill OpenRouter credit: refused unless SN15_ALLOW_CREDIT=1.

Credit tripwire (OpenRouter route; owner ruling 2026-11-07 08:40 "never bypass BYOK": no credit-billed call is acceptable, not
even one). OpenRouter falls back from the BYOK key to its own credit-billed Anthropic capacity when the key errors or is
rate-limited, unless the key's "Shared capacity fallback" is set to "Never use shared capacity" (is_byok_only / is_required, an
account setting: https://openrouter.ai/docs/guides/overview/auth/byok). No request field turns it off: `provider.only` +
`allow_fallbacks: false` (sent on every anthropic/* call) keep the request on provider Anthropic, and the fallback IS provider
Anthropic. Such a reply carries usage.cost > 0 / usage.is_byok false. Each one is appended to runs/live/credit_calls.jsonl (tool,
pid, argv, model, cost), printed on stderr and sent as a Slack alert (notify.py alert; log only where notify.py is absent: CI,
remote hosts). From the FIRST one every later call in the process is refused unsent (HTTP 402; with `raise_on_trip` the call
that tripped raises CreditSpent). SN15_ALLOW_CREDIT=1 is the owner-approved credit arm.

Never prints, logs or returns a key. Stdlib only.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
ROUTE_ENV = "SN15_LLM_ROUTE"
ALLOW_CREDIT_ENV = "SN15_ALLOW_CREDIT"
KEY_FILES = (
    "~/Documents/bittensor/sn15/.env",
    "~/.config/sn15/env",
    "~/sn15-ops/.env",
    "~/.sn15_env",
)
CREDIT_LOG = Path(os.environ.get("SN15_CREDIT_LOG") or Path.home() / "sn15-ops" / "runs" / "live" / "credit_calls.jsonl")
NOTIFY_PY = Path(os.environ.get("SN15_NOTIFY_PY") or Path.home() / ".cursor" / "skills" / "sn15-notify" / "scripts" / "notify.py")
BYOK_PIN = {"only": ["anthropic"], "allow_fallbacks": False}
# Anthropic's cap on cache breakpoints in one request; the earliest extra marks are dropped
MAX_CACHE_MARKS = 4
THINKING_BUDGET = {"minimal": 1024, "low": 1024, "medium": 2048, "high": 4096}

_LOCK = threading.Lock()
_STATE: dict[str, Any] = {"credit_calls": 0, "credit_usd": 0.0, "tripped": None, "announced": False}
_ALERT_HOOK: Any = None  # selftest only: receives the row instead of notify.py


class CreditSpent(RuntimeError):
    """An OpenRouter reply was billed to prepaid credit (or a call was refused after the tripwire fired)."""


# ------------------------------------------------------------------------------------------------------------- keys / route

def _key_from_files(name: str) -> str:
    for p in KEY_FILES:
        path = Path(os.path.expanduser(p))
        if not path.is_file():
            continue
        try:
            for line in path.read_text(errors="replace").splitlines():
                s = line.strip()
                if s.startswith("export "):
                    s = s[7:].strip()
                if s.startswith(name + "="):
                    val = s.split("=", 1)[1].strip().strip("'").strip('"')
                    if val:
                        return val
        except OSError:
            continue
    return ""


def anthropic_key() -> str:
    return (os.environ.get("ANTHROPIC_API_KEY") or "").strip() or _key_from_files("ANTHROPIC_API_KEY")


def openrouter_key() -> str:
    for k in ("OPENROUTER_API_KEY", "OR_API_KEY"):
        if (os.environ.get(k) or "").strip():
            return os.environ[k].strip()
    return _key_from_files("OPENROUTER_API_KEY")


def credit_allowed() -> bool:
    return os.environ.get(ALLOW_CREDIT_ENV) == "1"


def route_mode() -> str:
    mode = (os.environ.get(ROUTE_ENV) or "auto").strip().lower()
    return mode if mode in ("auto", "anthropic", "openrouter") else "auto"


def route_for(model: str) -> str:
    """'anthropic' (direct), 'openrouter' (BYOK pin + tripwire) or 'refuse:<why>' for one model id."""
    model = str(model or "")
    mode = route_mode()
    if not model.startswith("anthropic/"):
        if credit_allowed():
            return "openrouter"
        return "refuse:%s is not an Anthropic model: OpenRouter bills it to prepaid credit (set %s=1 for an owner-approved credit arm)" % (
            model or "(no model)", ALLOW_CREDIT_ENV)
    if mode == "openrouter":
        return "openrouter"
    if anthropic_key():
        return "anthropic"
    if mode == "anthropic":
        return "refuse:%s=anthropic but no ANTHROPIC_API_KEY is configured (env or %s)" % (ROUTE_ENV, ", ".join(KEY_FILES))
    return "openrouter"


def describe() -> str:
    """One line for logs: which route anthropic/* takes in this process (never the key)."""
    r = route_for("anthropic/claude-haiku-5.5")
    if r == "anthropic":
        return "anthropic/* -> api.anthropic.com direct (ANTHROPIC_API_KEY); OpenRouter not used"
    if r == "openrouter":
        why = "%s=openrouter" % ROUTE_ENV if route_mode() == "openrouter" else "no ANTHROPIC_API_KEY configured"
        return "anthropic/* -> OpenRouter, provider Anthropic BYOK pin + credit tripwire (%s)" % why
    return "anthropic/* refused: " + r[7:]


def require_route(model: str = "anthropic/claude-haiku-5.5") -> str:
    """For tools that used to fail early without an OpenRouter key: a non-empty route label, or SystemExit when no key at all."""
    r = route_for(model)
    if r.startswith("refuse:"):
        raise SystemExit(r[7:])
    if r == "openrouter" and not openrouter_key():
        raise SystemExit("no model key: neither ANTHROPIC_API_KEY nor OPENROUTER_API_KEY is configured (env or %s)" % ", ".join(KEY_FILES))
    return r


def anthropic_model_id(model: str) -> str:
    """anthropic/claude-haiku-5.5 -> claude-haiku-5-5 (Anthropic's own ids use dashes); SN15_ANTHROPIC_MODEL_MAP (JSON) overrides."""
    raw = os.environ.get("SN15_ANTHROPIC_MODEL_MAP")
    if raw:
        try:
            mapped = json.loads(raw).get(model)
            if mapped:
                return str(mapped)
        except ValueError:
            pass
    return model.split("/", 1)[-1].replace(".", "-")


# ------------------------------------------------------------------------------------------------- OpenAI -> Anthropic body

def _text_blocks(content: Any) -> list[dict]:
    if content is None:
        return []
    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content else []
    out: list[dict] = []
    for b in content if isinstance(content, list) else [content]:
        if isinstance(b, str):
            if b:
                out.append({"type": "text", "text": b})
        elif isinstance(b, dict) and b.get("type") in (None, "text") and isinstance(b.get("text"), str):
            if b["text"]:
                blk = {"type": "text", "text": b["text"]}
                if b.get("cache_control"):
                    blk["cache_control"] = b["cache_control"]
                out.append(blk)
        elif isinstance(b, dict) and b.get("type") == "image_url":
            url = str((b.get("image_url") or {}).get("url") or "")
            m = re.match(r"data:([^;]+);base64,(.*)$", url, re.S)
            if m:
                out.append({"type": "image", "source": {"type": "base64", "media_type": m.group(1), "data": m.group(2)}})
            elif url:
                out.append({"type": "image", "source": {"type": "url", "url": url}})
    return out


def _tool_id(raw: Any) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]", "_", str(raw or "call"))
    return s or "call"


def _push(msgs: list[dict], role: str, blocks: list[dict]) -> None:
    if not blocks:
        return
    if msgs and msgs[-1]["role"] == role:
        msgs[-1]["content"].extend(blocks)
    else:
        msgs.append({"role": role, "content": list(blocks)})


def _limit_cache_marks(payload: dict) -> None:
    marked: list[dict] = []
    for b in payload.get("system") or []:
        if isinstance(b, dict) and b.get("cache_control"):
            marked.append(b)
    for m in payload.get("messages") or []:
        for b in m.get("content") or []:
            if isinstance(b, dict) and b.get("cache_control"):
                marked.append(b)
    for b in marked[:-MAX_CACHE_MARKS] if len(marked) > MAX_CACHE_MARKS else []:
        b.pop("cache_control", None)


def to_anthropic(body: dict) -> tuple[dict, str | None]:
    """(Messages API payload, name of the tool standing in for response_format json_schema or None)."""
    system: list[dict] = []
    msgs: list[dict] = []
    for m in body.get("messages") or []:
        role = m.get("role")
        if role in ("system", "developer"):
            system.extend(_text_blocks(m.get("content")))
        elif role == "user":
            _push(msgs, "user", _text_blocks(m.get("content")))
        elif role == "assistant":
            blocks = _text_blocks(m.get("content"))
            for c in m.get("tool_calls") or []:
                fn = c.get("function") or {}
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args) if args.strip() else {}
                    except ValueError:
                        args = {}
                blocks.append({"type": "tool_use", "id": _tool_id(c.get("id")), "name": str(fn.get("name") or ""),
                               "input": args if isinstance(args, dict) else {}})
            _push(msgs, "assistant", blocks)
        elif role == "tool":
            inner = _text_blocks(m.get("content"))
            res: dict = {"type": "tool_result", "tool_use_id": _tool_id(m.get("tool_call_id"))}
            if any(b.get("cache_control") for b in inner):
                res["cache_control"] = {"type": "ephemeral"}
                for b in inner:
                    b.pop("cache_control", None)
            res["content"] = inner or [{"type": "text", "text": "(empty)"}]
            # tool results open the user turn that follows the assistant's calls
            if msgs and msgs[-1]["role"] == "user" and all(b.get("type") == "tool_result" for b in msgs[-1]["content"]):
                msgs[-1]["content"].append(res)
            else:
                msgs.append({"role": "user", "content": [res]})
    payload: dict = {"model": anthropic_model_id(str(body.get("model") or "")), "messages": msgs,
                     "max_tokens": int(body.get("max_tokens") or body.get("max_completion_tokens") or 1024)}
    if system:
        payload["system"] = system
    if body.get("temperature") is not None:
        payload["temperature"] = body["temperature"]
    if body.get("top_p") is not None:
        payload["top_p"] = body["top_p"]
    stop = body.get("stop")
    if stop:
        payload["stop_sequences"] = [stop] if isinstance(stop, str) else list(stop)
    tools = []
    for t in body.get("tools") or []:
        fn = t.get("function") if isinstance(t, dict) else None
        if isinstance(fn, dict) and fn.get("name"):
            tools.append({"name": fn["name"], "description": str(fn.get("description") or ""),
                          "input_schema": fn.get("parameters") or {"type": "object", "properties": {}}})
    json_tool = None
    rf = body.get("response_format") or {}
    if not tools and isinstance(rf, dict) and rf.get("type") == "json_schema":
        js = rf.get("json_schema") or {}
        json_tool = re.sub(r"[^A-Za-z0-9_-]", "_", str(js.get("name") or "respond"))[:64] or "respond"
        tools = [{"name": json_tool, "description": "Return the answer as this tool's input.",
                  "input_schema": js.get("schema") or {"type": "object"}}]
        payload["tool_choice"] = {"type": "tool", "name": json_tool}
    if tools:
        payload["tools"] = tools
        tc = body.get("tool_choice")
        if json_tool is None and tc is not None:
            if tc == "auto":
                payload["tool_choice"] = {"type": "auto"}
            elif tc == "required":
                payload["tool_choice"] = {"type": "any"}
            elif tc == "none":
                payload["tool_choice"] = {"type": "none"}
            elif isinstance(tc, dict) and (tc.get("function") or {}).get("name"):
                payload["tool_choice"] = {"type": "tool", "name": tc["function"]["name"]}
    reasoning = body.get("reasoning")
    forced = (payload.get("tool_choice") or {}).get("type") in ("tool", "any")
    # thinking is only legal with an auto / none tool choice, and a history that carries tool calls would need each turn's thinking
    # blocks back (the chat shape does not keep them): such calls go without thinking
    history_calls = any(b.get("type") == "tool_use" for mm in msgs for b in mm["content"])
    if isinstance(reasoning, dict) and reasoning.get("enabled") is not False and not forced and not history_calls and (
            reasoning.get("enabled") or reasoning.get("effort") or reasoning.get("max_tokens")):
        budget = int(reasoning.get("max_tokens") or THINKING_BUDGET.get(str(reasoning.get("effort") or "low"), 1024))
        payload["thinking"] = {"type": "enabled", "budget_tokens": max(1024, budget)}
        payload.pop("temperature", None)
        payload.pop("top_p", None)
        payload["max_tokens"] = max(payload["max_tokens"], payload["thinking"]["budget_tokens"] + 512)
    _limit_cache_marks(payload)
    return payload, json_tool


def from_anthropic(data: dict, asked_model: str, json_tool: str | None) -> dict:
    texts: list[str] = []
    thinking: list[str] = []
    calls: list[dict] = []
    for b in data.get("content") or []:
        t = b.get("type")
        if t == "text":
            texts.append(str(b.get("text") or ""))
        elif t == "thinking":
            thinking.append(str(b.get("thinking") or ""))
        elif t == "tool_use":
            if json_tool and b.get("name") == json_tool:
                texts.append(json.dumps(b.get("input") or {}))
            else:
                calls.append({"id": b.get("id"), "type": "function",
                              "function": {"name": b.get("name"), "arguments": json.dumps(b.get("input") or {})}})
    u = data.get("usage") or {}
    read = int(u.get("cache_read_input_tokens") or 0)
    write = int(u.get("cache_creation_input_tokens") or 0)
    prompt = int(u.get("input_tokens") or 0) + read + write
    message: dict = {"role": "assistant", "content": "".join(texts) if texts or not calls else None}
    if calls:
        message["tool_calls"] = calls
    if thinking:
        message["reasoning"] = "\n".join(thinking)
    stop = data.get("stop_reason")
    finish = {"end_turn": "stop", "stop_sequence": "stop", "tool_use": "tool_calls", "max_tokens": "length"}.get(stop, stop or "stop")
    if json_tool and finish == "tool_calls":
        finish = "stop"
    return {
        "id": data.get("id"), "object": "chat.completion", "model": asked_model, "provider": "Anthropic (direct)",
        "choices": [{"index": 0, "message": message, "finish_reason": finish, "native_finish_reason": stop}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": int(u.get("output_tokens") or 0),
                  "total_tokens": prompt + int(u.get("output_tokens") or 0),
                  "prompt_tokens_details": {"cached_tokens": read, "cache_write_tokens": write},
                  "cost": 0.0, "is_byok": True, "route": "anthropic-direct"},
    }


# --------------------------------------------------------------------------------------------------------------- transport

def _http_error(url: str, code: int, payload: Any) -> urllib.error.HTTPError:
    raw = json.dumps(payload).encode() if not isinstance(payload, (bytes, bytearray)) else bytes(payload)
    return urllib.error.HTTPError(url, int(code), "sn15 llm_route", None, io.BytesIO(raw))  # type: ignore[arg-type]


def _alert_credit(row: dict) -> str:
    """Slack alert for one credit-billed reply, detached so the caller never waits or fails on it; log only without notify.py."""
    if _ALERT_HOOK is not None:
        _ALERT_HOOK(row)
        return "alert hook"
    if not NOTIFY_PY.is_file():
        return "log only (notify.py absent)"
    import subprocess

    py = "/usr/bin/python3" if os.path.exists("/usr/bin/python3") else sys.executable
    title = "PREPAID CREDIT SPENT by %s" % row["tool"]
    body = ("• *Call*: %s served %s by %s, cost %.6f USD, is_byok %s, generation %s\n"
            "• *Process*: pid %s, argv %s\n"
            "• *State*: every later call in this process is refused (owner ruling 11-07 08:40: never bypass BYOK)\n"
            "• *Log*: %s" % (row["model"], row.get("served"), row.get("provider"), row["cost"], row.get("is_byok"),
                              row.get("generation"), row["pid"], " ".join(map(str, row["argv"])), CREDIT_LOG))
    try:
        subprocess.Popen([py, str(NOTIFY_PY), "alert", title, body, "--key", "credit-call-%s" % (row.get("generation") or row["epoch"])],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return "slack alert sent"
    except OSError as e:
        return "slack alert failed (%s), logged only" % e


def _note_credit(tool: str, model: str, data: dict) -> bool:
    """Record one credit-billed reply (log, stderr, Slack alert); True when it set this process's tripwire (always, unless the
    owner-approved credit arm is on)."""
    u = data.get("usage") or {}
    cost = float(u.get("cost") or 0.0)
    row = {"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "epoch": round(time.time(), 3), "tool": tool, "pid": os.getpid(),
           "argv": [os.path.basename(a) if i == 0 else a for i, a in enumerate(sys.argv[:4])], "model": model,
           "served": data.get("model"), "provider": data.get("provider"), "cost": cost, "is_byok": u.get("is_byok"),
           "generation": data.get("id")}
    with _LOCK:
        _STATE["credit_calls"] += 1
        _STATE["credit_usd"] += cost
        n = _STATE["credit_calls"]
        tripped = not credit_allowed()
        if tripped and not _STATE["tripped"]:
            _STATE["tripped"] = row
    try:
        CREDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with CREDIT_LOG.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass
    alert = _alert_credit(row)
    print("CREDIT CALL [%s]: OpenRouter billed prepaid credit $%.6f for %s (provider %s, is_byok %s); %d such call(s) in this process; %s%s" % (
        tool, cost, model, row["provider"], row["is_byok"], n, alert, " - TRIPWIRE SET: every later call is refused" if tripped else ""),
        file=sys.stderr, flush=True)
    return tripped


def credit_state() -> dict:
    with _LOCK:
        return dict(_STATE)


def post_json(body: dict, *, timeout: float = 60.0, tool: str = "", raise_on_trip: bool = True) -> dict:
    """Send one chat-completions body by the route above; returns the OpenAI-shaped reply. HTTP failures (either route, and the
    refusals here) raise urllib.error.HTTPError with a JSON body, like urlopen; a credit-billed reply that sets the tripwire raises
    CreditSpent when raise_on_trip."""
    tool = tool or os.path.basename(sys.argv[0] or "python")
    model = str(body.get("model") or "")
    route = route_for(model)
    if not _STATE["announced"]:
        _STATE["announced"] = True
        if os.environ.get("SN15_LLM_ROUTE_QUIET") != "1":
            print("[llm_route] %s" % describe(), file=sys.stderr, flush=True)
    if route.startswith("refuse:"):
        raise _http_error(OPENROUTER_URL, 403, {"error": {"message": route[7:], "code": 403}})
    if route == "anthropic":
        payload, json_tool = to_anthropic(body)
        req = urllib.request.Request(ANTHROPIC_URL, data=json.dumps(payload).encode("utf-8"), method="POST", headers={
            "x-api-key": anthropic_key(), "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return from_anthropic(data, model, json_tool)
    if _STATE["tripped"] and not credit_allowed():
        msg = {"error": {"message": "credit tripwire: a call in this process was billed to OpenRouter prepaid credit (%s); nothing more is sent" % (
            json.dumps({k: _STATE["tripped"].get(k) for k in ("tool", "model", "cost", "provider")})), "code": 402}}
        if raise_on_trip:
            raise CreditSpent(msg["error"]["message"])
        raise _http_error(OPENROUTER_URL, 402, msg)
    key = openrouter_key()
    if not key:
        raise _http_error(OPENROUTER_URL, 401, {"error": {"message": "no ANTHROPIC_API_KEY or OPENROUTER_API_KEY configured", "code": 401}})
    payload = dict(body)
    if model.startswith("anthropic/"):
        payload["provider"] = dict(BYOK_PIN)
    usage = payload.get("usage")
    payload["usage"] = dict(usage, include=True) if isinstance(usage, dict) else {"include": True}
    req = urllib.request.Request(OPENROUTER_URL, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    u = data.get("usage") if isinstance(data, dict) else None
    if isinstance(u, dict) and (float(u.get("cost") or 0.0) > 0 or u.get("is_byok") is False) and not credit_allowed():
        if _note_credit(tool, model, data) and raise_on_trip:
            raise CreditSpent("OpenRouter billed prepaid credit $%.6f for %s in %s (BYOK fallback to shared capacity); see %s" % (
                float(u.get("cost") or 0.0), model, tool, CREDIT_LOG))
    return data


def send(body: dict, *, timeout: float = 60.0, tool: str = "", raise_on_trip: bool = True) -> tuple[int, dict]:
    """post_json() as (status, data): HTTP errors come back as (code, parsed error body); transport errors as (503, ...)."""
    try:
        return 200, post_json(body, timeout=timeout, tool=tool, raise_on_trip=raise_on_trip)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", errors="replace") or "{}")
        except ValueError:
            return e.code, {"error": {"message": str(e)}}
    except CreditSpent:
        raise
    except Exception as e:  # network
        return 503, {"error": {"message": str(e)}}


def load_from(*dirs: str):
    """For modules that must also run where this file is absent (CI checkout, remote hosts): import it from the first dir that
    has it, else None (the caller keeps its own transport)."""
    import importlib.util

    for name in ("llm_route", "sn15_llm_route"):
        if sys.modules.get(name) is not None and hasattr(sys.modules[name], "post_json"):
            return sys.modules[name]  # one instance per process: the credit tripwire state is shared
    for d in dirs:
        p = Path(os.path.expanduser(d)) / "llm_route.py"
        if p.is_file():
            spec = importlib.util.spec_from_file_location("llm_route", str(p))
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            sys.modules["llm_route"] = sys.modules["sn15_llm_route"] = mod
            spec.loader.exec_module(mod)
            return mod
    return None


def selftest() -> int:
    """Both routes against a fake transport: no network, no key read from disk, the real credit log untouched."""
    import tempfile

    global CREDIT_LOG
    sent: list[tuple[str, dict, dict]] = []
    replies: list[dict] = []

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        sent.append((req.full_url, json.loads(req.data.decode()), {k.lower(): v for k, v in req.header_items()}))
        return _Resp(json.dumps(replies.pop(0)).encode())

    real_urlopen, real_log, real_env, real_kff, real_notify = urllib.request.urlopen, CREDIT_LOG, dict(os.environ), _key_from_files, NOTIFY_PY
    fails = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal fails
        fails += 0 if cond else 1
        print("%s %s%s" % ("PASS" if cond else "FAIL", name, (" - " + detail) if detail and not cond else ""))

    body = {"model": "anthropic/claude-haiku-5.5", "max_tokens": 300, "temperature": 0,
            "messages": [{"role": "system", "content": [{"type": "text", "text": "rules", "cache_control": {"type": "ephemeral"}}]},
                         {"role": "user", "content": [{"type": "text", "text": "brief"}]},
                         {"role": "assistant", "content": None, "tool_calls": [{"id": "toolu_01", "type": "function",
                                                                                "function": {"name": "search", "arguments": "{\"q\": \"x\"}"}}]},
                         {"role": "tool", "tool_call_id": "toolu_01", "content": [{"type": "text", "text": "rows", "cache_control": {"type": "ephemeral"}}]},
                         {"role": "user", "content": "status"}],
            "tools": [{"type": "function", "function": {"name": "search", "description": "d", "parameters": {"type": "object"}, "strict": True}}],
            "tool_choice": {"type": "function", "function": {"name": "search"}}, "reasoning": {"enabled": True}}
    try:
        with tempfile.TemporaryDirectory(dir=str(Path.home() / "sn15-ops" / "scratch")) as d:
            CREDIT_LOG = Path(d) / "credit_calls.jsonl"
            urllib.request.urlopen = fake_urlopen  # type: ignore[assignment]
            for k in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "OR_API_KEY", ROUTE_ENV, ALLOW_CREDIT_ENV, "SN15_LLM_ROUTE_QUIET"):
                os.environ.pop(k, None)
            os.environ["SN15_LLM_ROUTE_QUIET"] = "1"
            globals()["_key_from_files"] = lambda name: ""  # never read the real key files here

            # 1. direct Anthropic route
            os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"
            replies.append({"id": "msg_1", "content": [{"type": "tool_use", "id": "toolu_02", "name": "search", "input": {"q": "y"}}],
                            "stop_reason": "tool_use", "usage": {"input_tokens": 10, "cache_read_input_tokens": 90, "output_tokens": 7}})
            out = post_json(body, tool="selftest")
            url, p, h = sent[-1]
            check("anthropic route: api.anthropic.com, never openrouter", url == ANTHROPIC_URL and "authorization" not in h and h.get("x-api-key") == "test-anthropic-key")
            check("model id claude-haiku-5-5", p["model"] == "claude-haiku-5-5", p["model"])
            check("system blocks keep cache_control", p["system"][0].get("cache_control") == {"type": "ephemeral"})
            roles = [m["role"] for m in p["messages"]]
            check("alternating roles user/assistant/user", roles == ["user", "assistant", "user"], str(roles))
            tr = p["messages"][2]["content"]
            check("tool_result first in its turn, status after", tr[0]["type"] == "tool_result" and tr[0]["tool_use_id"] == "toolu_01" and tr[-1]["text"] == "status")
            check("forced tool -> tool_choice tool, no thinking", p.get("tool_choice") == {"type": "tool", "name": "search"} and "thinking" not in p)
            check("tools -> input_schema, strict dropped", p["tools"][0] == {"name": "search", "description": "d", "input_schema": {"type": "object"}})
            m = out["choices"][0]["message"]
            check("reply -> OpenAI tool_calls", m["tool_calls"][0]["function"] == {"name": "search", "arguments": "{\"q\": \"y\"}"} and out["choices"][0]["finish_reason"] == "tool_calls")
            check("usage: prompt incl cache, cost 0", out["usage"]["prompt_tokens"] == 100 and out["usage"]["prompt_tokens_details"]["cached_tokens"] == 90 and out["usage"]["cost"] == 0.0)

            js = {"model": "anthropic/claude-haiku-4.5", "messages": [{"role": "user", "content": "q"}], "max_tokens": 50,
                  "response_format": {"type": "json_schema", "json_schema": {"name": "decisions_result", "schema": {"type": "object"}}}}
            replies.append({"content": [{"type": "tool_use", "id": "t", "name": "decisions_result", "input": {"scores": {"a": 1.0}}}],
                            "stop_reason": "tool_use", "usage": {"input_tokens": 5, "output_tokens": 3}})
            out = post_json(js, tool="selftest")
            check("json_schema -> forced tool, content is the JSON", json.loads(out["choices"][0]["message"]["content"]) == {"scores": {"a": 1.0}}
                  and sent[-1][1]["tool_choice"] == {"type": "tool", "name": "decisions_result"})

            loop = {"model": "anthropic/claude-haiku-5.5", "messages": [{"role": "user", "content": "go"}], "max_tokens": 800,
                    "temperature": 0, "tools": body["tools"], "tool_choice": "auto", "reasoning": {"enabled": True}}
            replies.append({"content": [{"type": "thinking", "thinking": "plan"}, {"type": "text", "text": "ok"}], "stop_reason": "end_turn", "usage": {}})
            out = post_json(loop, tool="selftest")
            p = sent[-1][1]
            check("loop reasoning -> thinking, temperature dropped, max_tokens > budget",
                  p.get("thinking", {}).get("type") == "enabled" and "temperature" not in p and p["max_tokens"] > p["thinking"]["budget_tokens"])
            check("thinking -> message.reasoning", out["choices"][0]["message"].get("reasoning") == "plan")

            # 2. OpenRouter route (no Anthropic key): pin + tripwire
            os.environ.pop("ANTHROPIC_API_KEY")
            os.environ["OPENROUTER_API_KEY"] = "test-or-key"
            replies.append({"choices": [{"message": {"content": "a"}}], "usage": {"cost": 0, "is_byok": True}})
            post_json({"model": "anthropic/claude-haiku-5.5", "messages": [{"role": "user", "content": "x"}]}, tool="selftest")
            url, p, h = sent[-1]
            check("no Anthropic key -> OpenRouter with Anthropic BYOK pin", url == OPENROUTER_URL and p["provider"] == {"only": ["anthropic"], "allow_fallbacks": False} and p["usage"]["include"] is True)
            check("BYOK reply ($0) does not trip", not _STATE["tripped"] and _STATE["credit_calls"] == 0)
            replies.append({"choices": [{"message": {"content": "a"}}], "usage": {"cost": 0, "is_byok": True}})
            post_json({"model": "anthropic/claude-haiku-5.5", "provider": {"order": ["azure"]}, "messages": []}, tool="selftest")
            check("a caller's own provider block is replaced by the pin", sent[-1][1]["provider"] == {"only": ["anthropic"], "allow_fallbacks": False})

            # first credit-billed reply (a 0.0003 USD BYOK fallback): logged + alerted, tripwire set, later calls refused unsent
            alerts: list[dict] = []
            globals()["_ALERT_HOOK"] = alerts.append
            replies.append({"id": "gen-1", "choices": [{"message": {"content": "a"}}], "usage": {"cost": 0.0003, "is_byok": False}, "provider": "Anthropic"})
            try:
                post_json({"model": "anthropic/claude-haiku-5.5", "messages": [{"role": "user", "content": "x"}]}, tool="selftest")
                check("first credit-billed reply (0.0003) raises CreditSpent", False)
            except CreditSpent:
                check("first credit-billed reply (0.0003) raises CreditSpent", _STATE["tripped"] is not None)
            rows = [json.loads(x) for x in CREDIT_LOG.read_text().splitlines()]
            check("credit call logged with tool + cost", len(rows) == 1 and rows[0]["tool"] == "selftest" and rows[0]["cost"] == 0.0003)
            check("credit call alerted once", len(alerts) == 1 and alerts[0]["generation"] == "gen-1")
            n_sent = len(sent)
            try:
                post_json({"model": "anthropic/claude-haiku-5.5", "messages": [{"role": "user", "content": "x"}]}, tool="selftest")
                check("after the first credit call nothing is sent", False)
            except CreditSpent:
                check("after the first credit call nothing is sent", len(sent) == n_sent)
            st, data = send({"model": "anthropic/claude-haiku-5.5", "messages": []}, tool="selftest", raise_on_trip=False)
            check("raise_on_trip=False -> 402 unsent", st == 402 and len(sent) == n_sent and "credit tripwire" in json.dumps(data))
            _STATE.update(credit_calls=0, credit_usd=0.0, tripped=None)

            # world_sim shape (raise_on_trip=False): the billed reply is returned, logged, alerted; the next call is refused 402
            replies.append({"id": "gen-2", "choices": [{"message": {"content": "b"}}], "usage": {"cost": 0.0003, "is_byok": False}})
            st, data = send({"model": "anthropic/claude-haiku-5.5", "messages": []}, tool="world_sim:agent", raise_on_trip=False)
            st2, _ = send({"model": "anthropic/claude-haiku-5.5", "messages": []}, tool="world_sim:agent", raise_on_trip=False)
            check("simulator: billed reply returned once, then 402 unsent", st == 200 and st2 == 402 and len(alerts) == 2 and len(sent) == n_sent + 1)
            _STATE.update(credit_calls=0, credit_usd=0.0, tripped=None)
            n_sent = len(sent)

            # no notify.py (CI, remote hosts): log only, the caller is not failed by the alert
            globals()["_ALERT_HOOK"] = None
            globals()["NOTIFY_PY"] = Path(d) / "absent_notify.py"
            replies.append({"id": "gen-3", "choices": [{"message": {"content": "c"}}], "usage": {"cost": 0.0003, "is_byok": False}})
            st, data = send({"model": "anthropic/claude-haiku-5.5", "messages": []}, tool="ci", raise_on_trip=False)
            check("notify.py absent -> log only, no exception", st == 200 and _alert_credit({"tool": "ci"}) == "log only (notify.py absent)"
                  and len(CREDIT_LOG.read_text().splitlines()) == 3)
            _STATE.update(credit_calls=0, credit_usd=0.0, tripped=None)
            n_sent = len(sent)
            os.environ[ALLOW_CREDIT_ENV] = "1"
            replies.append({"id": "gen-4", "choices": [{"message": {"content": "d"}}], "usage": {"cost": 0.0003, "is_byok": False}})
            st, data = send({"model": "anthropic/claude-haiku-5.5", "messages": []}, tool="armed", raise_on_trip=False)
            check("SN15_ALLOW_CREDIT=1 (owner arm): no tripwire", st == 200 and not _STATE["tripped"])
            os.environ.pop(ALLOW_CREDIT_ENV)
            n_sent = len(sent)

            st, data = send({"model": "google/gemini-3.8-flash", "messages": []}, tool="selftest")
            check("non-Anthropic model refused unsent (403)", st == 403 and len(sent) == n_sent)
            os.environ[ROUTE_ENV] = "anthropic"
            st, data = send({"model": "anthropic/claude-haiku-5.5", "messages": []}, tool="selftest")
            check("SN15_LLM_ROUTE=anthropic without a key refuses (no OpenRouter fallback)", st == 403 and len(sent) == n_sent)
    finally:
        urllib.request.urlopen = real_urlopen  # type: ignore[assignment]
        CREDIT_LOG = real_log
        os.environ.clear()
        os.environ.update(real_env)
        globals()["_key_from_files"] = real_kff
        globals()["NOTIFY_PY"] = real_notify
        globals()["_ALERT_HOOK"] = None
        _STATE.update(credit_calls=0, credit_usd=0.0, tripped=None, announced=False)
    print("llm_route self-test: %d failure(s)" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    # llm_route.py route | translate <body.json> | selftest     (no model call; no key printed)
    _a = sys.argv[1:]
    if _a and _a[0] == "selftest":
        raise SystemExit(selftest())
    if not _a or _a[0] == "route":
        print(describe())
        print("anthropic key configured: %s | openrouter key configured: %s | %s=%s | %s=%s" % (
            bool(anthropic_key()), bool(openrouter_key()), ROUTE_ENV, route_mode(), ALLOW_CREDIT_ENV, os.environ.get(ALLOW_CREDIT_ENV, "")))
    elif _a[0] == "translate" and len(_a) > 1:
        print(json.dumps(to_anthropic(json.loads(Path(_a[1]).read_text()))[0], indent=1)[:4000])
    else:
        print(__doc__)
