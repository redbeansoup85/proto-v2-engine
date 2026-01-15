from __future__ import annotations

import json
import os
import re
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Tuple, List


VERSION_RE = re.compile(r"policy_v(\d{4})\.json$")


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_of_obj(obj: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(obj)).hexdigest()


@dataclass(frozen=True)
class PolicySnapshot:
    version: int
    path: str
    policy: Dict[str, Any]
    sha256: str


class PolicyStore:
    """
    File-based policy store:
      data/policies/policy_v0001.json
      data/policies/policy_v0002.json
      ...
    """

    def __init__(self, dirpath: str = "data/policies") -> None:
        self.dirpath = dirpath
        os.makedirs(self.dirpath, exist_ok=True)

    def _list_versions(self) -> List[Tuple[int, str]]:
        items: List[Tuple[int, str]] = []
        for fn in os.listdir(self.dirpath):
            m = VERSION_RE.search(fn)
            if not m:
                continue
            v = int(m.group(1))
            items.append((v, os.path.join(self.dirpath, fn)))
        items.sort(key=lambda x: x[0])
        return items

    def latest(self) -> PolicySnapshot:
        versions = self._list_versions()
        if not versions:
            raise FileNotFoundError(f"No policy versions found in {self.dirpath}. Create policy_v0001.json first.")
        v, path = versions[-1]
        policy = self._load_json(path)
        return PolicySnapshot(version=v, path=path, policy=policy, sha256=sha256_of_obj(policy))

    def load_version(self, version: int) -> PolicySnapshot:
        path = os.path.join(self.dirpath, f"policy_v{version:04d}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        policy = self._load_json(path)
        return PolicySnapshot(version=version, path=path, policy=policy, sha256=sha256_of_obj(policy))

    def save_new_version(self, policy: Dict[str, Any]) -> PolicySnapshot:
        latest = self.latest()
        new_v = latest.version + 1
        path = os.path.join(self.dirpath, f"policy_v{new_v:04d}.json")
        self._save_json(path, policy)
        return PolicySnapshot(version=new_v, path=path, policy=policy, sha256=sha256_of_obj(policy))

    @staticmethod
    def _load_json(path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _save_json(path: str, obj: Any) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
