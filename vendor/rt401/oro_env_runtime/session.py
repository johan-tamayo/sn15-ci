"""The validator-facing session (open, tools, step, forced finish, ledger) and grading."""

from __future__ import annotations

import dataclasses
import json

from dataclasses import dataclass
from . import RUNTIME_CONTRACT, LEDGER_FORMAT, VERDICT_FORMAT, canonical, schema
from .models import Reader
from .pack import Pack
from .sandbox import ENVIRONMENT_TRIPS, BoundTrip, RuntimeConfig, Sandbox, prng_key

CATEGORIES = (
    "request not met", "needs not found", "changes missed",
    "process requirement missed", "not the best option", "did not finish",
)
WORLD_ERROR = "world error"
ENVIRONMENT_FAULT = "environment fault"
ARG_DEPTH = 64  # nesting allowed in agent tool arguments
_ARGS_DETAIL = (f"arguments must be a JSON object within the size limit, integers in the signed 64-bit range, nested at most "
                f"{ARG_DEPTH} deep")
_RERUN_DEADLINE = 4  # how many times longer the re-run of an environment trip may take per entry call


class SessionClosed(RuntimeError):
    """step() or finish() after the episode has finished."""


@dataclass(frozen=True)
class StepResult:
    observation: object
    finished: bool


class Session:
    """One episode. `read` serves outside calls, e.g. models.live_reader(...)."""

    def __init__(self, pack: Pack, task_id: str, episode_nonce: str, read: Reader, config: RuntimeConfig = RuntimeConfig()) -> None:
        self.pack, self.read, self.config = pack, read, config
        self.task = pack.tasks[task_id]
        self.tools_by_name = {t["name"]: t for t in pack.tools}
        self.records: list[dict] = []
        self.steps = self.turns = 0
        self.finished = False
        self.opening: object = None
        self._accepted: dict | None = None
        m = pack.manifest
        self._append({
            "kind": "open", "pack_id": m["pack_id"], "world_id": m["world_id"], "delivery": m["delivery"],
            "manifest_sha256": pack.manifest_sha256,
            "runtime_contract": RUNTIME_CONTRACT, "task_id": task_id, "task_sha256": self.task["sha256"], "episode_nonce": episode_nonce,
        })
        self.box: Sandbox | None = None
        try:
            self.box = Sandbox(pack, ticks=pack.limits["call_ticks"], key=prng_key(m["pack_id"], task_id, episode_nonce),
                               on_records=self.records.extend, on_call=self._call_out, config=config)
            envelope = {k: self.task[k] for k in ("task_id", "request_text", "params")}
            self.opening, _ = self._entry("start", [envelope])
            self._append({"kind": "start", "observation": self.opening})
        except BoundTrip as trip:
            self._trip(trip)
        except BaseException:  # never leave a worker behind: the caller gets no session to close
            if self.box is not None:
                self.box.close()
            raise

    @property
    def request_text(self) -> str:
        return self.task["request_text"]

    def tools(self) -> list[dict]:
        """Agent-visible tool declarations (no handler ids)."""
        return [{k: t[k] for k in ("name", "description", "parameters")} for t in self.pack.tools]

    def step(self, tool: str, args: object) -> StepResult:
        """Route one agent tool call."""
        if self.finished:
            raise SessionClosed("the episode has finished")
        self.steps += 1
        try:
            try:  # a canonical copy (the caller may reuse its object), integral numbers as integers
                raw = canonical.dumps(canonical.check(args, ARG_DEPTH))
            except (canonical.NotCanonical, RecursionError):
                raw = b""
            # Nothing over the size limit is recorded, as sent or as recorded: the ledger goes to grading whole.
            size = self.pack.limits["max_arg_bytes"]
            recorded_args = json.loads(raw, parse_float=_number) if 0 < len(raw) <= size else None
            if recorded_args is not None and len(canonical.dumps(recorded_args)) > size:
                recorded_args = None
            named = canonical.is_text(tool) and (tool in self.tools_by_name or len(tool.encode()) <= size)
            self._append({"kind": "action", "step": self.steps, "tool": tool if named else None, "args": recorded_args})
            self._turn()
            observation = self._route(tool, recorded_args)
        except BoundTrip as trip:
            self._trip(trip)
            return StepResult(None, True)
        except BaseException:  # never leave a worker behind
            self.box.close()
            raise
        self._append({"kind": "observation", "step": self.steps, "observation": observation})
        limits = self.pack.limits
        if self._accepted is not None:
            self._close(self._accepted["kind"], order=self._accepted)
        elif self.steps >= limits["max_steps"] or self.turns >= limits["max_turns"]:
            self._close("limit")
        return StepResult(observation, self.finished)

    def finish(self) -> None:
        """Runtime-forced finish when the validator stops the episode."""
        if self.finished:
            raise SessionClosed("the episode has finished")
        self._close("stopped")

    def ledger(self) -> dict:
        return {"ledger_format": LEDGER_FORMAT, "episode": list(self.records), "grading": []}

    def _route(self, tool: object, args: object) -> object:
        spec = self.tools_by_name.get(tool) if isinstance(tool, str) else None
        if spec is None:
            return {"error": "unknown_tool"}
        if not isinstance(args, dict):
            return {"error": "invalid_arguments", "detail": _ARGS_DETAIL}
        try:
            schema.validate(args, spec["parameters"])
        except schema.Invalid as exc:
            return {"error": "invalid_arguments", "detail": str(exc)}
        if not self.box.action_cost(spec["name"], self._counters()):
            return {"error": "budget_exceeded"}
        observation, order = self._entry("call", [spec["handler"], args])
        if order is None:
            return observation
        self._turn()
        verdict, _ = self._entry("can_finish", [order])
        self._append({"kind": "finish_check", "order": order, "ok": verdict["ok"], "observation": verdict["observation"]})
        if verdict["ok"]:
            self._accepted = order
            return observation
        return {"observation": observation, "refusal": verdict["observation"]}

    def _turn(self) -> None:
        self.turns += 1
        self._entry("turn", [])

    def _counters(self) -> dict:
        return {"step": self.steps, "turn": self.turns}

    def _entry(self, name: str, args: list) -> tuple[object, dict | None]:
        return self.box.entry(name, args, self._counters())

    def _call_out(self, service: str, request: dict) -> dict:
        result = self.read(service, request)
        self._append({"kind": "reading", "service": service, "request": request, "result": result})
        return result

    def _append(self, record: dict) -> None:
        self.records.append(canonical.check(record))

    def _trip(self, trip: BoundTrip) -> None:
        """A deterministic trip ends the episode as "bound". An environment trip is re-run once from the recorded
        inputs with a longer deadline: an environment fault if the re-run does not trip, else "bound"."""
        reason = "bound"
        if trip.kind in ENVIRONMENT_TRIPS:
            config = dataclasses.replace(self.config, entry_seconds=self.config.entry_seconds * _RERUN_DEADLINE)
            header = self.records[0]
            rerun = _Rerun(self.pack, header["task_id"], header["episode_nonce"], _recorded_then(self.records, self.read), config)
            for record in self.records:
                if record["kind"] == "action" and not rerun.finished:
                    rerun.step(record["tool"], record["args"])
            if not rerun.finished:
                rerun.finish()
            reason = "bound" if rerun.records[-1]["reason"] == "bound" else "environment"
        self._close(reason, bound=trip.kind)

    def _close(self, reason: str, *, order: dict | None = None, bound: str | None = None) -> None:
        record = {"kind": "finish", "reason": reason, "order": order, "steps": self.steps, "turns": self.turns}
        if bound is not None:
            record["bound"] = bound
        self._append(record)
        self.finished = True
        if self.box is not None:
            self.box.close()


class _Rerun(Session):
    """The one re-run of an environment trip: any trip in it is final."""

    def _trip(self, trip: BoundTrip) -> None:
        self._close("bound", bound=trip.kind)


def _number(text: str) -> int | float:
    """A JSON number with a fraction or exponent: an integer if it is integral and in the i64 range."""
    value = float(text)
    return int(value) if value.is_integer() and canonical.I64_MIN <= value <= canonical.I64_MAX else value


def _recorded_then(records: list[dict], read: Reader) -> Reader:
    """Serve the recorded readings in order while the requests match, then `read`."""
    recorded = iter([r for r in records if r["kind"] == "reading"])

    def serve(service: str, request: dict) -> dict:
        r = next(recorded, None)
        return r["result"] if r is not None and (r["service"], r["request"]) == (service, request) else read(service, request)

    return serve


def grade_episode(pack: Pack, ledger: dict, read: Reader, config: RuntimeConfig = RuntimeConfig()) -> dict:
    """Run the pack's grader over a closed ledger; fill ledger["grading"] and return the verdict."""
    episode = ledger["episode"]
    header, finish = episode[0], episode[-1]
    readings: list[dict] = []
    flags: list[str] = []
    if finish["reason"] == "environment":
        score, category, flags = None, ENVIRONMENT_FAULT, ["environment_fault"]  # not scored: the episode is re-run
    elif finish["reason"] == "bound":
        score, category, flags = 0.0, "did not finish", ["possible_world_defect"]  # the grader is not run
    else:
        try:
            result = _grade(pack, episode, read, config, readings)
        except BoundTrip as trip:
            result = None
            if trip.kind in ENVIRONMENT_TRIPS:  # re-run once from the recorded readings with a longer deadline
                first, readings = readings, []
                longer = dataclasses.replace(config, entry_seconds=config.entry_seconds * _RERUN_DEADLINE)
                try:
                    result = _grade(pack, episode, _recorded_then(first, read), longer, readings)
                except BoundTrip:
                    pass
        score, category = _check_grade(result)
        if category == WORLD_ERROR:
            flags = ["world_error"]
    ledger["grading"] = readings
    return {
        "verdict_format": VERDICT_FORMAT, "pack_id": pack.pack_id, "task_id": header["task_id"],
        "ledger_sha256": canonical.digest(episode),
        "grading_sha256": canonical.digest(readings), "score": score, "category": category, "flags": flags,
    }


def _grade(pack: Pack, episode: list[dict], read: Reader, config: RuntimeConfig, readings: list[dict]) -> object:
    """One grading run in its own worker; its readings are appended to `readings`."""
    def record(service: str, request: dict) -> dict:
        result = read(service, request)
        readings.append({"kind": "reading", "service": service, "request": request, "result": result})
        return result

    header, finish = episode[0], episode[-1]
    box = None
    try:
        box = Sandbox(pack, ticks=pack.limits["grade_ticks"], key=prng_key(pack.pack_id, header["task_id"], header["episode_nonce"]),
                      on_records=lambda records: None, on_call=record, config=config)
        return box.entry("grade", [episode, pack.answers[header["task_id"]]["answer"]], {"step": finish["steps"], "turn": finish["turns"]})[0]
    finally:
        if box is not None:
            box.close()


def _check_grade(result: object) -> tuple[float, str | None]:
    """Exactly {score in [0, 1], category None or from CATEGORIES}; anything else is a world error."""
    if (isinstance(result, dict) and set(result) == {"score", "category"}
            and isinstance(result["score"], (int, float)) and not isinstance(result["score"], bool)
            and 0 <= result["score"] <= 1 and (result["category"] is None or result["category"] in CATEGORIES)):
        return float(result["score"]), result["category"]
    return 0.0, WORLD_ERROR
