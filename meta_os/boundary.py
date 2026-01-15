from __future__ import annotations
import os


class BoundaryViolation(RuntimeError):
    pass


def mode() -> str:
    # 정확히 하나만 켜지게 강제
    sandbox = os.getenv("SANDBOX_MODE", "").strip() in ("1", "true", "TRUE", "yes", "YES")
    core = os.getenv("CORE_MODE", "").strip() in ("1", "true", "TRUE", "yes", "YES")
    if sandbox and core:
        raise BoundaryViolation("Both SANDBOX_MODE and CORE_MODE are set. Choose exactly one.")
    if sandbox:
        return "sandbox"
    if core:
        return "core"
    # 기본값: sandbox (안전)
    return "sandbox"


def require_sandbox() -> None:
    if mode() != "sandbox":
        raise BoundaryViolation("This operation is sandbox-only.")


def require_core() -> None:
    if mode() != "core":
        raise BoundaryViolation("This operation is core-only.")


def deny_in_sandbox(feature: str) -> None:
    """
    sandbox에서 '외부 서비스/자동화/외부 사용자 대상' 성격의 기능 호출을 막는다.
    """
    if mode() == "sandbox":
        raise BoundaryViolation(f"Denied in sandbox: {feature}")


def vault_root() -> str:
    """
    vault 루트도 모드별로 분리. 실수로 섞이는 것 자체를 원천 차단.
    """
    m = mode()
    if m == "sandbox":
        return os.getenv("SANDBOX_VAULT_ROOT", "vault")  # 현행 유지(내부 실험)
    return os.getenv("CORE_VAULT_ROOT", "core_vault")     # core는 별도 디렉토리

