from __future__ import annotations

from fastapi import APIRouter, Depends

from infra.api.deps import get_scene_repo

router = APIRouter(prefix="/v1/scenes", tags=["scenes"])


@router.get("/active")
def list_active(scenes=Depends(get_scene_repo)) -> dict:
    return {"active_index": scenes.list_active()}


@router.get("/active/by-context/{context_key}")
def get_active_by_context(context_key: str, scenes=Depends(get_scene_repo)) -> dict:
    ref = scenes.get_active_by_context(context_key)
    if ref is None:
        return {"scene": None}
    # dataclass -> dict
    return {
        "scene": {
            "scene_id": ref.scene_id,
            "status": ref.status.value if hasattr(ref.status, "value") else str(ref.status),
            "context": {
                "org_id": ref.context.org_id,
                "site_id": ref.context.site_id,
                "channel": ref.context.channel.value if hasattr(ref.context.channel, "value") else ref.context.channel,
                "context_key": ref.context.context_key,
            },
            "ts_start": ref.ts_start,
            "ts_end": ref.ts_end,
        }
    }
