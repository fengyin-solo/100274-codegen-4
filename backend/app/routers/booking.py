"""订舱受理接口：按航线、托运人定位订舱；过滤明细与票数统计与列表同源。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, BookingPageResult, EntryPayload
from app.services.booking import BookingService

router = APIRouter(prefix="/api/booking", tags=["订舱受理"])

service = BookingService()

LIST_FIELDS = ["订舱号", "托运人名称", "航线", "起运港", "目的港", "船名航次", "箱型箱量", "截关时间", "提交时间", "订舱状态"]


@router.get("/summary")
def booking_summary() -> dict[str, object]:
    """其他入口的票数统一从这里读，与订舱列表共用同一套过滤口径。"""
    return service.summary()


@router.get("", response_model=BookingPageResult)
def list_bookings(
    route: str | None = Query(default=None, description="航线，选中即过滤"),
    shipper: str | None = Query(default=None, description="托运人，选中即过滤"),
    page: int = 1,
    size: int = 20,
) -> BookingPageResult:
    """按航线与托运人定位订舱，按截关时间从近到远排列；过滤掉的记录随响应逐条说明。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if page < 1:
        page = 1
    items, total, excluded, options = service.list_bookings(
        route=route, shipper=shipper, page=page, size=size
    )
    return BookingPageResult(
        items=items,
        total=total,
        page=page,
        size=size,
        excluded=excluded,
        options=options,
    )


@router.post("", response_model=ActionResult)
def create_booking(payload: EntryPayload) -> ActionResult:
    """登记一条新提交的订舱（重复提交、信息不全也允许落库，由受理列表口径过滤点名）。"""
    entry, missing = service.create_booking(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="订舱已提交，等待受理", entry=entry)


@router.get("/{entry_id}", response_model=dict)
def get_booking(entry_id: int) -> dict:
    """读取单票订舱明细，同时标注它是否可受理及被过滤的原因。"""
    entry = service.get_booking(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"订舱 {entry_id} 不存在或已归档")
    return entry


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单票可受理订舱执行受理；重复提交、已释放、信息不全的记录会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.accept(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
