from __future__ import annotations

from pathlib import Path

import core.governance.constitution_refs as refs


def _repo_root() -> Path:
    # proto-v2-engine repo root
    return Path(__file__).resolve().parents[1]


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_constitution_refs_paths_exist() -> None:
    """
    Fail-closed:
    - constitution_refs.py에 등록된 문서 경로 상수는 반드시 실제 파일이어야 한다.
    """
    root = _repo_root()

    candidates = [
        ("CONSTITUTION_AQ_PATH", getattr(refs, "CONSTITUTION_AQ_PATH", None)),
        ("AMENDMENT_PLAYBOOK_PATH", getattr(refs, "AMENDMENT_PLAYBOOK_PATH", None)),
    ]

    missing = []
    for name, rel in candidates:
        if not rel:
            missing.append(f"{name} is missing in core/governance/constitution_refs.py")
            continue

        p = root / Path(rel)
        if not p.exists():
            missing.append(f"{name} -> '{rel}' does not exist on disk")
        elif not p.is_file():
            missing.append(f"{name} -> '{rel}' exists but is not a file")

    assert not missing, "Constitution refs integrity failed:\n- " + "\n- ".join(missing)


def test_constitution_AQ_links_amendment_playbook() -> None:
    """
    Fail-closed:
    - constitution_AQ.md 는 amendment_playbook.md 를 '명시적으로' 참조해야 한다.
    - 링크 방식은 (1) 경로 문자열 포함 또는 (2) 파일명 문자열 포함을 허용
    """
    root = _repo_root()

    aq_rel = getattr(refs, "CONSTITUTION_AQ_PATH", None)
    playbook_rel = getattr(refs, "AMENDMENT_PLAYBOOK_PATH", None)

    assert aq_rel, "CONSTITUTION_AQ_PATH must be defined"
    assert playbook_rel, "AMENDMENT_PLAYBOOK_PATH must be defined"

    aq_path = root / Path(aq_rel)
    pb_path = root / Path(playbook_rel)

    assert aq_path.exists(), f"constitution_AQ missing: {aq_rel}"
    assert pb_path.exists(), f"amendment_playbook missing: {playbook_rel}"

    aq = _read_text(aq_path)
    pb_filename = Path(playbook_rel).name

    if playbook_rel in aq:
        return
    if pb_filename in aq:
        return

    raise AssertionError(
        "constitution_AQ must explicitly reference amendment_playbook.\n"
        f"- expected to find '{playbook_rel}' or '{pb_filename}' in {aq_rel}"
    )


def test_change_classification_tokens_declared_in_AQ() -> None:
    """
    Fail-closed:
    - constitution_AQ.md 에 A-MAJOR / A-MINOR / A-PATCH 토큰 선언이 존재해야 한다.
    """
    root = _repo_root()

    aq_rel = getattr(refs, "CONSTITUTION_AQ_PATH", None)
    assert aq_rel, "CONSTITUTION_AQ_PATH must be defined"

    aq_path = root / Path(aq_rel)
    assert aq_path.exists(), f"constitution_AQ missing: {aq_rel}"

    aq = _read_text(aq_path)

    required_tokens = ["A-MAJOR", "A-MINOR", "A-PATCH"]
    missing = [t for t in required_tokens if t not in aq]
    assert not missing, f"Missing classification tokens in {aq_rel}: {missing}"
