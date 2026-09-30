"""订舱受理接口：按航线与托运人定位订舱，并给出被过滤记录的明确说明。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, BookingPageResult, EntryPayload
from app.services.booking import BookingService

router = APIRouter(prefix="/api/booking", tags=["订舱受理"])

service = BookingService()


@router.get("", response_model=BookingPageResult)
def list_entries(
    route: str | None = Query(default=None, description="航线名称，如 远东-欧洲"),
    shipper: str | None = Query(default=None, description="托运人代码，如 SH001"),
    page: int = 1,
    size: int = 10,
) -> BookingPageResult:
    """按航线/托运人过滤订舱，截关时间从近到远排列；过滤掉的记录随 excluded 返回。"""
    if page < 1:
        raise HTTPException(status_code=400, detail="页码需从 1 开始")
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total, pending_total, excluded = service.list_entries(route=route, shipper=shipper, page=page, size=size)
    return BookingPageResult(
        items=items,
        total=total,
        page=page,
        size=size,
        pending_total=pending_total,
        excluded=excluded,
    )


@router.get("/options")
def filter_options() -> dict[str, object]:
    """航线与托运人下拉选项，与受理列表同源。"""
    return service.filter_options()


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单票订舱明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"订舱 {entry_id} 不存在或已归档")
    return entry


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单票订舱执行受理；重复受理等不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
