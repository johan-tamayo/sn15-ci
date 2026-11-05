"""One sandboxed worker process per episode or grading run."""

from __future__ import annotations

import hashlib
import json
import os
import selectors
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable

from . import canonical
from .pack import PackRefused


@dataclass(frozen=True)
class RuntimeConfig:
    """Validator-side safety limits. Tripping one is an environment trip: never scored unless a re-run trips again."""

    memory_bytes: int = 1 << 30
    entry_seconds: float = 10.0


# Trips of the validator's machine rather than of the pack code and its inputs (see `Session`).
ENVIRONMENT_TRIPS = frozenset({"wall", "memory", "crash"})


class BoundTrip(Exception):
    """Pack code exceeded a bound or failed; `kind` is steps or error, or one of ENVIRONMENT_TRIPS."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


def prng_key(pack_id: str, task_id: str, episode_nonce: str) -> str:
    return hashlib.sha256("\0".join((pack_id, task_id, episode_nonce)).encode()).hexdigest()


class Sandbox:
    def __init__(self, pack, *, ticks: int, key: str, on_records: Callable[[list[dict]], None],
                 on_call: Callable[[str, dict], dict], config: RuntimeConfig) -> None:
        self.config, self.on_records, self.on_call = config, on_records, on_call
        # A missing or truncated catalog file is the host's fault, never the episode's: refuse before any worker starts.
        try:
            present = os.stat(pack.catalog_file).st_size == pack.catalog_size
        except (OSError, ValueError):
            present = False
        if not present:
            raise PackRefused("the pack's catalog file is missing or changed since it was verified")
        self.proc = subprocess.Popen([sys.executable, "-I", "-m", "oro_env_runtime._worker"], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, close_fds=True)
        self._buf = b""
        rest = canonical.dumps({"code": pack.code, "indexes": {name: ix["id"] for name, ix in pack.indexes.items()}, "prng_key": key, "ticks": ticks,
                                "max_callstack": pack.limits["max_callstack"], "memory_bytes": config.memory_bytes})
        self._write(b'{"catalog":' + pack.catalog_ref_json + b"," + rest[1:])  # "catalog" sorts first: the bytes `canonical.dumps` gives
        self._await()

    def entry(self, name: str, args: list, counters: dict) -> tuple[object, dict | None]:
        """Call an entry point; return (result, finish request or None)."""
        self._send({"op": "entry", "entry": name, "args": args, "counters": counters})
        reply = self._await()
        return reply["result"], reply["finish"]

    def action_cost(self, tool: str, counters: dict) -> bool:
        """Charge the costs declared for `tool`; False if a budget refuses the action."""
        self._send({"op": "action_cost", "tool": tool, "counters": counters})
        return self._await()["result"]

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait()
        try:
            self.proc.stdin.close()
        except OSError:  # unflushed input to a worker that has gone
            pass
        self.proc.stdout.close()

    def _send(self, msg: dict) -> None:
        self._write(canonical.dumps(msg))

    def _write(self, line: bytes) -> None:
        try:
            self.proc.stdin.write(line + b"\n")
            self.proc.stdin.flush()
        except OSError:
            self._trip("crash")

    def _await(self) -> dict:
        while True:
            msg = json.loads(self._readline(time.monotonic() + self.config.entry_seconds))
            self.on_records(msg["records"])
            if msg["op"] == "call_out":
                self._send({"op": "result", "result": self.on_call(msg["service"], msg["request"])})
            elif msg["op"] == "trip":
                self._trip(msg["kind"])
            else:
                return msg

    def _trip(self, kind: str):
        self.close()
        raise BoundTrip(kind)

    def _readline(self, deadline: float) -> bytes:
        fd = self.proc.stdout.fileno()
        with selectors.DefaultSelector() as sel:
            if os.name != "nt":  # Windows cannot select on pipes: no deadline there
                sel.register(fd, selectors.EVENT_READ)
            while b"\n" not in self._buf:
                if os.name != "nt" and not sel.select(max(0.0, deadline - time.monotonic())):
                    self._trip("wall")
                chunk = os.read(fd, 1 << 16)
                if not chunk:
                    self._trip("crash")
                self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line
