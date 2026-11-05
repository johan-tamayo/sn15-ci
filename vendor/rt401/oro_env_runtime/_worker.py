"""Sandbox worker: runs a pack's Starlark code and serves its runtime API over canonical-JSON lines."""

from __future__ import annotations

import functools
import hashlib
import json
import mmap
import sys

import starlark as sl

from oro_env_runtime import canonical

RUNTIME_FUNCTIONS = (
    "catalog_get", "search", "state_get", "state_set", "counters", "basket_get", "basket_set",
    "request_order", "request_decline", "send_message", "model_call", "model_decide", "ledger_append",
    "set_cost", "set_budget", "charge", "meters", "rand_below",
)


@functools.cache
def _mapped(file: str, sha256: str):
    """The pack's catalog file mapped read-only (shared with every other worker through the page cache) and checked
    against its manifest sha256; once per process, so a forked worker reuses its parent's mapping."""
    with open(file, "rb") as f:
        mapped = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) if f.seek(0, 2) else b""
    if hashlib.sha256(mapped).hexdigest() != sha256:
        raise RuntimeError("the catalog file changed after the pack was verified")
    return mapped


def _catalog(ref: dict):
    """The mapped catalog and its id -> (offset, length) index."""
    return _mapped(ref["file"], ref["sha256"]), {k: tuple(v) for k, v in ref["index"].items()}


def _sorted_keys(pairs: list) -> dict:
    """Keys in sorted order, as the canonical JSON workers got before 4.0.1 (a repeated key: the last wins)."""
    return dict(sorted(pairs, key=lambda pair: pair[0]))


class Runtime:
    def __init__(self, init: dict, out, inp) -> None:
        self.out, self.inp = out, inp
        self._catalog_file, self._catalog_index = _catalog(init["catalog"])
        self.indexes: dict[str, str] = init["indexes"]
        self.max_ticks: int = init["ticks"]
        self.prng_key = bytes.fromhex(init["prng_key"])
        self.prng_counter = 0
        self.state: dict = {}
        self.basket: dict[str, int] = {}
        self.costs: dict[str, list[tuple[str, int]]] = {}
        self.budgets: dict[str, int] = {}
        self.used: dict[str, int] = {}
        self.count = {"step": 0, "turn": 0}
        self.records: list[dict] = []
        self.finish: dict | None = None
        self.ticks = 0
        self.options = sl.EvalOptions(check_cancelled=self._tick, max_callstack_size=init["max_callstack"])
        module = sl.Module()
        for name in RUNTIME_FUNCTIONS:
            module.add_callable(name, getattr(self, name))
        dialect = sl.Dialect.standard()
        dialect.enable_load = False
        sl.eval_with(self.options, module, sl.parse("world/code/main.star", init["code"], dialect), sl.Globals.standard())
        self.program = module.freeze()

    def _tick(self) -> bool:
        self.ticks += 1
        return self.ticks > self.max_ticks

    def _record(self, kind: str, **fields) -> None:
        self.records.append(canonical.check({"kind": kind, **fields}))

    def send(self, msg: dict) -> None:
        msg["records"], self.records = self.records, []
        self.out.write(canonical.dumps(msg) + b"\n")
        self.out.flush()

    def entry(self, name: str, args: list) -> object:
        return canonical.check(self.program.call_with(self.options, name, *args).value)

    # runtime API (each name in RUNTIME_FUNCTIONS)
    def catalog_get(self, listing_id):
        at = self._catalog_index.get(listing_id)
        return None if at is None else json.loads(self._catalog_file[at[0]:at[0] + at[1]], object_pairs_hook=_sorted_keys)

    def search(self, index, query, params=None):
        return self._call_out("search", {"index": self.indexes[index], "query": query, "params": params or {}})

    def state_get(self, key, default=None):
        return self.state.get(key, default)

    def state_set(self, key, value):
        self.state[key] = canonical.check(value)

    def counters(self):
        return dict(self.count)

    def basket_get(self):
        return [{"id": i, "quantity": q} for i, q in self.basket.items()]

    def basket_set(self, listing_id, quantity):
        if listing_id not in self._catalog_index:
            raise ValueError("basket_set: unknown listing id")
        if quantity:
            self.basket[listing_id] = quantity
        else:
            self.basket.pop(listing_id, None)
        self._record("basket", id=listing_id, quantity=quantity)

    def request_order(self, lines):
        self.finish = {"kind": "order", "lines": [{"id": ln["id"], "quantity": ln["quantity"]} for ln in lines]}

    def request_decline(self):
        self.finish = {"kind": "decline"}

    def send_message(self, text):
        self._record("message", text=text)
        reply = self.program.call_with(self.options, "message", text).value
        self._record("reply", text=reply)
        return reply

    def model_call(self, model, prompt, params=None):
        return self._call_out("complete", {"model": model, "prompt": prompt, "params": params or {}})

    def model_decide(self, model, state, questions, params=None):
        return self._call_out("decide", {"model": model, "state": state, "questions": questions, "params": params or {}})

    def _call_out(self, service: str, request: dict) -> dict:
        self.send({"op": "call_out", "service": service, "request": request})
        return json.loads(self.inp.readline())["result"]

    def ledger_append(self, record):
        self._record("event", data=record)

    def set_cost(self, tool, meter, amount):
        self.costs.setdefault(tool, []).append((meter, amount))
        self._record("cost", tool=tool, meter=meter, amount=amount)

    def set_budget(self, meter, budget):
        self.budgets[meter] = budget
        self._record("budget", meter=meter, budget=budget)

    def charge(self, meter, amount):
        return self.charge_all([(meter, amount)])

    def charge_all(self, items: list[tuple[str, int]]) -> bool:
        totals: dict[str, int] = {}
        for meter, amount in items:
            totals[meter] = totals.get(meter, 0) + amount
        ok = not any(m in self.budgets and self.used.get(m, 0) + a > self.budgets[m] for m, a in totals.items())
        for meter, amount in totals.items():
            if ok:
                self.used[meter] = self.used.get(meter, 0) + amount
            self._record("charge", meter=meter, amount=amount, used=self.used.get(meter, 0), ok=ok)
        return ok

    def meters(self):
        return {m: {"used": self.used.get(m, 0), "budget": self.budgets.get(m)} for m in sorted(set(self.used) | set(self.budgets))}

    def rand_below(self, n):
        limit = (1 << 64) - (1 << 64) % n
        while True:
            block = hashlib.sha256(self.prng_key + self.prng_counter.to_bytes(8, "big")).digest()
            self.prng_counter += 1
            value = int.from_bytes(block[:8], "big")
            if value < limit:
                self._record("draw", n=n, value=value % n)
                return value % n


def _trip_kind(exc: BaseException, ticks_exceeded: bool) -> str:
    """By state and exception type only: messages can carry pack data and agent strings."""
    if ticks_exceeded:
        return "steps"
    if isinstance(exc, MemoryError) or not isinstance(exc, Exception):  # a Rust panic: allocation failure
        return "memory"
    return "error"  # Starlark errors, the call-stack limit included


def main() -> None:
    inp, out = sys.stdin.buffer, sys.stdout.buffer
    init = json.loads(inp.readline())
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (init["memory_bytes"], init["memory_bytes"]))
    except (ImportError, ValueError, OSError):
        pass  # best effort off Linux
    runtime = Runtime(init, out, inp)
    runtime.send({"op": "ready"})
    for line in iter(inp.readline, b""):
        request = json.loads(line)
        runtime.count = request["counters"]
        runtime.ticks, runtime.finish = 0, None
        try:
            if request["op"] == "action_cost":
                result: object = runtime.charge_all(runtime.costs.get(request["tool"], []))
            else:
                result = runtime.entry(request["entry"], request["args"])
            runtime.send({"op": "done", "result": result, "finish": runtime.finish})
        except BaseException as exc:  # Starlark errors and Rust panics (PanicException)
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            runtime.send({"op": "trip", "kind": _trip_kind(exc, runtime.ticks > runtime.max_ticks)})


if __name__ == "__main__":
    main()
