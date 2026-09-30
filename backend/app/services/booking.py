"""订舱受理业务规则：受理口径、重复提交去重、筛选与排序都收在这里。

受理列表的唯一口径是 ``accepted_scope``：舱位已释放、托运人信息不全的先滤掉，
同一票订舱重复提交只认第一次受理（提交时间最早）的一条。
列表、看板待受理票数、航线/托运人选项都从这里取数，保证多个入口同源。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "booking"

# 托运人信息不全：托运人代码、名称、联系人、联系电话缺任一项都不予受理
SHIPPER_REQUIRED_FIELDS = ["托运人代码", "托运人名称", "联系人", "联系电话"]
# 舱位一旦释放，订舱不再进入受理列表
RELEASED_CABIN = "已释放"
ACTION_RULES = {"受理订舱": "已受理"}
STATUS_ORDER = ["待受理", "已受理"]

LIST_FIELDS = [
    "订舱号",
    "航线",
    "托运人代码",
    "托运人名称",
    "联系人",
    "联系电话",
    "船名航次",
    "箱型尺寸",
    "箱量",
    "截关时间",
    "提交时间",
    "舱位状态",
]


def _parse_time(value: Any) -> datetime:
    """把 'YYYY-MM-DD HH:MM' 截关/提交时间解析成可比较的值；解析不了按最早处理。"""
    text = str(value or "").strip()
    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return datetime.min


def _is_blank(value: Any) -> bool:
    return not str(value if value is not None else "").strip()


class BookingService:
    def accepted_scope(
        self,
        *,
        route: str | None = None,
        shipper: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """按受理口径返回（保留的订舱，过滤掉的订舱说明）。

        顺序与受理口径一致：先在当前航线/托运人范围内滤掉舱位已释放、托运人信息
        不全的，再在剩余记录里按订舱号去重（同号保留提交时间最早、其次 id 最小的
        一条），最后按截关时间从近到远排列。
        """
        rows = store.rows(MODULE)

        def match_dimensions(row: dict[str, Any]) -> bool:
            if route and row.get("航线") != route:
                return False
            if shipper and row.get("托运人代码") != shipper:
                return False
            return True

        candidates = [row for row in rows if match_dimensions(row)]

        valid: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        # 第一道：舱位释放、托运人信息不全先过滤
        for row in candidates:
            reason = self._base_exclude_reason(row)
            if reason:
                excluded.append(self._excluded_item(row, reason))
            else:
                valid.append(row)

        # 第二道：同订舱号只留第一次受理（提交时间最早，并列时 id 最小）的一条
        earliest_by_no: dict[str, dict[str, Any]] = {}
        for row in valid:
            booking_no = str(row.get("订舱号") or "").strip()
            current = earliest_by_no.get(booking_no)
            if current is None:
                earliest_by_no[booking_no] = row
                continue
            current_key = (_parse_time(current.get("提交时间")), int(current.get("id", 0)))
            row_key = (_parse_time(row.get("提交时间")), int(row.get("id", 0)))
            if row_key < current_key:
                earliest_by_no[booking_no] = row

        kept: list[dict[str, Any]] = []
        for row in valid:
            winner = earliest_by_no.get(str(row.get("订舱号") or "").strip())
            if winner is not None and winner is not row:
                reason = (
                    f"重复提交，只认第一次受理（{winner.get('提交时间')} 提交的一条"
                    f"，订舱 id {winner.get('id')}）"
                )
                excluded.append(self._excluded_item(row, reason))
            else:
                kept.append(row)

        kept.sort(key=lambda r: (_parse_time(r.get("截关时间")), int(r.get("id", 0))))
        excluded.sort(key=lambda item: int(item.get("id") or 0))
        return kept, excluded

    def _excluded_item(self, row: dict[str, Any], reason: str) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "订舱号": row.get("订舱号"),
            "航线": row.get("航线"),
            "托运人代码": row.get("托运人代码"),
            "托运人名称": row.get("托运人名称"),
            "提交时间": row.get("提交时间"),
            "截关时间": row.get("截关时间"),
            "过滤原因": reason,
        }

    def _base_exclude_reason(self, row: dict[str, Any]) -> str:
        if str(row.get("舱位状态") or "").strip() == RELEASED_CABIN:
            return "舱位已释放"
        missing = [field for field in SHIPPER_REQUIRED_FIELDS if _is_blank(row.get(field))]
        if missing:
            return f"托运人信息不全（缺少：{'、'.join(missing)}）"
        return ""

    def acceptance_block(self, row: dict[str, Any]) -> str:
        """单票订舱能否受理：与列表口径同源，明细页和受理动作共用。"""
        base = self._base_exclude_reason(row)
        if base:
            return base
        booking_no = str(row.get("订舱号") or "").strip()
        valid = [
            other
            for other in store.rows(MODULE)
            if str(other.get("订舱号") or "").strip() == booking_no
            and not self._base_exclude_reason(other)
        ]
        winner = min(
            valid,
            key=lambda r: (_parse_time(r.get("提交时间")), int(r.get("id", 0))),
            default=None,
        )
        if winner is not None and winner is not row:
            return (
                f"重复提交，只认第一次受理（{winner.get('提交时间')} 提交的一条"
                f"，订舱 id {winner.get('id')}）"
            )
        return ""

    def list_entries(
        self,
        *,
        route: str | None = None,
        shipper: str | None = None,
        page: int = 1,
        size: int = 10,
    ) -> tuple[list[dict[str, Any]], int, int, list[dict[str, Any]]]:
        kept, excluded = self.accepted_scope(route=route, shipper=shipper)
        total = len(kept)
        pending_total = sum(1 for row in kept if row.get("pending"))
        start = max(page - 1, 0) * size
        page_rows = [
            {field: row.get(field) for field in LIST_FIELDS}
            | {"id": row.get("id"), "status": row.get("status"), "pending": row.get("pending")}
            for row in kept[start:start + size]
        ]
        return page_rows, total, pending_total, excluded

    def filter_options(self) -> dict[str, list[dict[str, str]]]:
        """航线与托运人下拉选项，同样基于受理口径取数，避免选到全被过滤掉的组合。"""
        kept, _ = self.accepted_scope()
        routes: dict[str, None] = {}
        shippers: dict[str, dict[str, str]] = {}
        for row in kept:
            route = str(row.get("航线") or "").strip()
            if route:
                routes.setdefault(route, None)
            code = str(row.get("托运人代码") or "").strip()
            if code and code not in shippers:
                shippers[code] = {"value": code, "label": f"{code} {row.get('托运人名称') or ''}".strip()}
        return {
            "routes": [{"value": name, "label": name} for name in sorted(routes)],
            "shippers": [shippers[code] for code in sorted(shippers)],
        }

    def pending_count(self) -> int:
        """待受理票数：与列表同源，另一个入口（看板）直接读这个数。"""
        kept, _ = self.accepted_scope()
        return sum(1 for row in kept if row.get("pending"))

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        # 明细页据此禁用受理按钮：口径与列表完全一致
        detail = dict(entry)
        detail["不可受理原因"] = self.acceptance_block(entry)
        return detail

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"订舱 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于订舱受理可执行范围"
        target = ACTION_RULES[action]
        if entry.get("status") == target:
            return None, "该订舱已经受理，请勿重复操作"
        block = self.acceptance_block(entry)
        if block:
            return None, f"该订舱不能受理：{block}"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        return entry, "订舱已受理"
