"""订舱受理业务规则：过滤口径、重复提交去重、截关排序与受理流转都收在这里。

口径约定（任何入口读票数都必须走本模块，保证与订舱列表同源）：

1. 同一票订舱（按订舱号）重复提交时，只认提交时间最早的一条作为受理对象，
   后到的重复提交一律过滤，并注明保留的是哪一条；
2. 舱位已经释放的订舱先过滤掉；
3. 托运人名称、联系人、联系电话任一缺失视为托运人信息不全，先过滤掉；
4. 存活下来的订舱按截关时间从近到远排列。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "booking"
SHIPPER_FIELDS = ["托运人名称", "托运人联系人", "托运人联系电话"]
STATUS_ORDER = ["待受理", "已受理"]
ACTION_RULES = {"受理": "已受理"}
TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, TIME_FORMAT)
    except ValueError:
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None


class BookingService:
    # ---- 核心口径：所有入口共用这一条管线 ---------------------------------

    def _classify(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[int, list[dict[str, Any]]]]:
        """把原始订舱分成「可受理」与「已过滤」两组，并给出每条的过滤原因。

        返回：(可受理列表, 已过滤列表, 原始 id -> 判定信息映射)。
        """
        rows = store.rows(MODULE)
        decisions: dict[int, dict[str, Any]] = {
            int(row["id"]): {"canonical": False, "reasons": [], "recognized_id": None}
            for row in rows
        }

        # 第一步：按订舱号分组，只认提交时间最早的一条（同时间再按 id 兜底）。
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            groups.setdefault(str(row.get("订舱号") or ""), []).append(row)
        for booking_no, group in groups.items():
            ordered = sorted(group, key=lambda r: (_parse_time(r.get("提交时间")) or datetime.max, int(r["id"])))
            recognized = ordered[0]
            decisions[int(recognized["id"])]["canonical"] = True
            for duplicate in ordered[1:]:
                decision = decisions[int(duplicate["id"])]
                decision["canonical"] = False
                decision["recognized_id"] = int(recognized["id"])
                decision["reasons"].append(
                    f"同一票订舱重复提交，仅保留首次受理记录 #{recognized['id']}"
                    f"（该票最早提交于 {recognized.get('提交时间') or '—'}）"
                )

        # 第二步：在所有原始行上检查托运人完整性与舱位释放，命中即过滤。
        canonical: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        for row in rows:
            entry_id = int(row["id"])
            decision = decisions[entry_id]
            missing = [field for field in SHIPPER_FIELDS if not str(row.get(field) or "").strip()]
            if missing:
                decision["reasons"].append(f"托运人信息不全（缺少：{'、'.join(missing)}）")
            if bool(row.get("舱位释放")):
                decision["reasons"].append("舱位已经释放")
            if decision["canonical"] and not decision["reasons"]:
                canonical.append(row)
            else:
                excluded.append({
                    "id": entry_id,
                    "订舱号": row.get("订舱号"),
                    "托运人名称": row.get("托运人名称"),
                    "航线": row.get("航线"),
                    "提交时间": row.get("提交时间"),
                    "截关时间": row.get("截关时间"),
                    "reasons": list(decision["reasons"]),
                    "过滤原因": "；".join(decision["reasons"]) or "未被认定为该票订舱的首次受理记录",
                })

        # 第三步：可受理订舱按截关时间从近到远排列，缺失时间的排末尾。
        canonical.sort(key=lambda r: (_parse_time(r.get("截关时间")) is None, _parse_time(r.get("截关时间")) or datetime.max, int(r["id"])))
        excluded.sort(key=lambda item: int(item["id"]))
        return canonical, excluded, decisions

    def _options(self, canonical: list[dict[str, Any]]) -> dict[str, list[str]]:
        """筛选项始终取自当前可受理集合，避免选中注定查不到的条件。"""
        routes = sorted({str(row["航线"]) for row in canonical if row.get("航线")})
        shippers = sorted({str(row["托运人名称"]) for row in canonical if row.get("托运人名称")})
        return {"航线": routes, "托运人": shippers}

    # ---- 列表与明细 ---------------------------------------------------------

    def list_bookings(
        self,
        *,
        route: str | None = None,
        shipper: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]], dict[str, list[str]]]:
        canonical, excluded, _ = self._classify()
        options = self._options(canonical)
        if route:
            canonical = [row for row in canonical if str(row.get("航线") or "") == route]
        if shipper:
            canonical = [row for row in canonical if str(row.get("托运人名称") or "") == shipper]
        total = len(canonical)
        start = max(page - 1, 0) * size
        items = canonical[start:start + size]
        return items, total, excluded, options

    def get_booking(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        if row is None:
            return None
        _, _, decisions = self._classify()
        decision = decisions.get(entry_id)
        result = dict(row)
        if decision is not None:
            result["可受理"] = decision["canonical"] and not decision["reasons"]
            result["过滤原因"] = list(decision["reasons"])
            result["首次受理记录"] = decision["recognized_id"]
        return result

    # ---- 受理流转 -----------------------------------------------------------

    def accept(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于订舱受理可执行范围"
        row = store.find(MODULE, entry_id)
        if row is None:
            return None, f"订舱 {entry_id} 不存在或已归档"
        _, _, decisions = self._classify()
        decision = decisions.get(entry_id)
        if decision is None or not decision["canonical"] or decision["reasons"]:
            reasons = decision["reasons"] if decision else ["订舱不在可受理集合"]
            return None, f"该订舱不能受理：{'；'.join(reasons) or '不是该票订舱的首次受理记录'}"
        if row.get("status") == STATUS_ORDER[-1]:
            return None, "该订舱已受理，请勿重复操作"
        row["status"] = ACTION_RULES[action]
        row["pending"] = False
        row["abnormal"] = False
        return row, f"订舱 {row.get('订舱号')} 已受理"

    def create_booking(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """登记一条新提交的订舱；托运人信息允许先缺着，受理列表会把它过滤并点名。"""
        required = ["订舱号", "航线", "截关时间"]
        missing = [field for field in required if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        carried = [
            "订舱号", "托运人名称", "托运人联系人", "托运人联系电话",
            "航线", "起运港", "目的港", "船名航次", "箱型箱量", "截关时间", "提交时间",
        ]
        for field in carried:
            entry[field] = values.get(field)
        if not str(entry.get("提交时间") or "").strip():
            entry["提交时间"] = datetime.now().strftime(TIME_FORMAT)
        entry["舱位释放"] = False
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = any(not str(entry.get(field) or "").strip() for field in SHIPPER_FIELDS)
        rows.append(entry)
        return entry, []

    # ---- 同源统计：其他入口（运营概览等）通过这里拿票数 ----------------------

    def summary(self) -> dict[str, Any]:
        canonical, excluded, _ = self._classify()
        return {
            "total": len(canonical),
            "pending": sum(1 for row in canonical if row.get("status") == "待受理"),
            "accepted": sum(1 for row in canonical if row.get("status") == "已受理"),
            "excluded": len(excluded),
        }
