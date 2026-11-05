"""Outside services called by pack code (model completions, model decisions, search); the runtime owns timeouts and retries."""

from __future__ import annotations

import queue
import threading
from typing import Callable, Protocol

from . import canonical


class ModelClient(Protocol):
    def complete(self, model: str, prompt: str, params: dict, timeout: float) -> str: ...

    def decide(self, model: str, state: object, questions: object, params: dict, timeout: float) -> object: ...


class SearchClient(Protocol):
    def search(self, index_id: str, query: str, params: dict, timeout: float) -> list[tuple[str, float]]: ...


def _complete(models: ModelClient, search: SearchClient, r: dict, timeout: float) -> dict:
    text = models.complete(r["model"], r["prompt"], r["params"], timeout)
    if not isinstance(text, str):
        raise TypeError("completion is not text")
    return {"ok": True, "text": text}


def _decide(models: ModelClient, search: SearchClient, r: dict, timeout: float) -> dict:
    return {"ok": True, "answers": canonical.check(models.decide(r["model"], r["state"], r["questions"], r["params"], timeout))}


def _search(models: ModelClient, search: SearchClient, r: dict, timeout: float) -> dict:
    hits = search.search(r["index"], r["query"], r["params"], timeout)
    return {"ok": True, "hits": canonical.check([{"id": i, "score": float(s)} for i, s in hits])}


SERVICES = {"complete": _complete, "decide": _decide, "search": _search}
Reader = Callable[[str, dict], dict]


def live_reader(models: ModelClient, search: SearchClient, timeout: float, retries: int) -> Reader:
    """read(service, request) -> {"ok": true, ...} or {"ok": false, "error": "timeout" | "error"}."""
    def read(service: str, request: dict) -> dict:
        error = "error"
        for _ in range(retries + 1):
            outcome: queue.Queue = queue.Queue()

            def attempt(outcome: queue.Queue = outcome) -> None:  # its own queue: a late attempt never answers the next
                try:
                    outcome.put(SERVICES[service](models, search, request, timeout))
                except Exception:  # a provider or server failure of any kind is a value for pack code
                    outcome.put(None)

            # A daemon thread: a client that ignores its timeout cannot hold up the process's exit.
            threading.Thread(target=attempt, daemon=True).start()
            try:
                result = outcome.get(timeout=timeout)
            except queue.Empty:
                error = "timeout"
                continue
            if result is not None:
                return result
            error = "error"
        return {"ok": False, "error": error}

    return read
