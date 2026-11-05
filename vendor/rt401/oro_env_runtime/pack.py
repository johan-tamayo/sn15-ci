"""Loading and verifying a signed world pack."""

from __future__ import annotations

import base64
import importlib.metadata
import json
from dataclasses import dataclass
from functools import cached_property
from importlib import resources
from pathlib import Path, PurePosixPath

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from . import RUNTIME_CONTRACT, PACK_FORMAT, canonical

SIGNING_CONTEXT = b"oro-world-pack/1\n"
Keyring = dict[str, Ed25519PublicKey]


class PackRefused(ValueError):
    """The pack cannot be verified and must not run."""


@dataclass(frozen=True)
class Pack:
    manifest: dict
    manifest_sha256: str
    code: str
    tools: list[dict]
    catalog: dict[str, dict]
    indexes: dict[str, dict]  # name -> {"id": archive sha256, "archive": path, "settings": opaque}
    tasks: dict[str, dict]
    answers: dict[str, dict]
    # Where each session's worker reads listings: the verified catalog file, its sha256 and each id's
    # (offset, length) line. Workers share the file through the page cache instead of each parsing it.
    catalog_file: str = ""
    catalog_size: int = -1
    catalog_sha256: str = ""
    catalog_index: dict[str, tuple[int, int]] | None = None

    @property
    def pack_id(self) -> str:
        return self.manifest["pack_id"]

    @property
    def limits(self) -> dict:
        return self.manifest["limits"]

    @cached_property
    def catalog_ref_json(self) -> bytes:
        """What each session's worker gets instead of the catalog, serialised once for all of them."""
        return canonical.dumps({"file": self.catalog_file, "sha256": self.catalog_sha256,
                                "index": {k: list(v) for k, v in (self.catalog_index or {}).items()}})


def parse_keyring(doc: dict) -> Keyring:
    return {e["key_id"]: Ed25519PublicKey.from_public_bytes(base64.b64decode(e["public_key"])) for e in doc["keys"]}


def pinned_keyring() -> Keyring:
    return parse_keyring(json.loads(resources.files("oro_env_runtime").joinpath("keys.json").read_text()))


def signed_bytes(manifest: dict) -> bytes:
    return SIGNING_CONTEXT + canonical.dumps({k: v for k, v in manifest.items() if k != "signature"})


def load_pack(root: Path, keyring: Keyring | None = None) -> Pack:
    """Verify the pack at `root` (default keyring: the pinned one) and parse it; raise PackRefused."""
    root = Path(root)
    manifest_bytes = (root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("pack_format") != PACK_FORMAT:
        raise PackRefused(f"unknown pack_format {manifest.get('pack_format')!r}")
    if manifest.get("runtime_contract") != RUNTIME_CONTRACT:
        raise PackRefused(f"unsupported runtime_contract {manifest.get('runtime_contract')!r}")
    sig = manifest.get("signature") or {}
    key = (pinned_keyring() if keyring is None else keyring).get(sig.get("key_id"))
    if key is None or sig.get("algorithm") != "ed25519":
        raise PackRefused("unsigned, or signed by a key not in the keyring")
    try:
        key.verify(base64.b64decode(sig["value"]), signed_bytes(manifest))
    except (InvalidSignature, ValueError) as exc:
        raise PackRefused("signature does not verify") from exc
    installed = importlib.metadata.version("starlark-pyo3")
    if manifest["sandbox"]["version"] != installed:
        raise PackRefused(f"sandbox {manifest['sandbox']['version']} unsupported (installed {installed})")
    data: dict[str, bytes] = {}
    for rel, digest in manifest["parts"].items():
        try:
            data[rel] = (root / rel).read_bytes()
        except OSError as exc:
            raise PackRefused(f"{rel}: missing") from exc
        if canonical.sha256_hex(data[rel]) != digest:
            raise PackRefused(f"{rel}: checksum mismatch")
    catalog, catalog_index, at = {}, {}, 0
    for line in data["world/catalog.jsonl"].splitlines(keepends=True):
        body = line.rstrip(b"\r\n")
        item = json.loads(body)
        catalog[item["id"]], catalog_index[item["id"]] = item, (at, len(body))
        at += len(line)
    canonical.check(catalog)  # what workers read: checked once here, not on every lookup
    parsed: dict[str, dict] = {"tasks/": {}, "answers/": {}}
    indexes: dict[str, dict] = {}
    for rel in sorted(data):
        if rel.startswith("world/index/") and rel.endswith(".json"):
            doc = json.loads(data[rel])  # {"archive": part path, "settings": opaque}
            indexes[PurePosixPath(rel).stem] = {"id": manifest["parts"][doc["archive"]], "archive": str(root / doc["archive"]),
                                                "settings": doc["settings"]}
        for prefix, into in parsed.items():
            if rel.startswith(prefix):
                into[PurePosixPath(rel).stem] = json.loads(data[rel])
    return Pack(manifest, canonical.sha256_hex(manifest_bytes), data["world/code/main.star"].decode(),
                json.loads(data["world/tools.json"])["tools"], catalog, indexes, parsed["tasks/"], parsed["answers/"],
                str((root / "world/catalog.jsonl").resolve()), len(data["world/catalog.jsonl"]),
                manifest["parts"]["world/catalog.jsonl"], catalog_index)
