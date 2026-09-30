"""港口集装箱作业管理平台 后端服务入口。

启动：uvicorn app.main:app --host 127.0.0.1 --port 8000
健康检查：GET /api/health
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import ROUTERS
from app.services.booking import BookingService
from app.store import store

app = FastAPI(title="港口集装箱作业管理平台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in ROUTERS:
    app.include_router(module.router)


@app.get("/api/health")
def health() -> dict[str, object]:
    """健康检查：确认服务已经监听、示例数据已经就绪。"""
    return {"ok": True, "app": settings.app_name, "modules": len(store.module_names())}


@app.get("/api/overview")
def overview() -> dict[str, object]:
    """运营概览：把各业务模块的待处理量汇总成看板卡片。

    订舱受理的票数改走 BookingService.summary()，与订舱列表共用过滤口径，
    避免概览把重复提交、已释放、信息不全的订舱也算成待受理。
    """
    data = store.overview()
    booking_summary = BookingService().summary()
    modules = []
    for item in data["modules"]:
        if item["name"] == "booking":
            modules.append({
                "name": item["name"],
                "created": booking_summary["total"],
                "pending": booking_summary["pending"],
                "abnormal": booking_summary["excluded"],
            })
        else:
            modules.append(item)
    cards = [
        {"label": "业务模块", "value": len(modules)},
        {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
        {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
        {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
    ]
    return {"cards": cards, "modules": modules, "booking_summary": booking_summary}
