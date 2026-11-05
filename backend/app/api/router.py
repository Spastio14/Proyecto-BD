from fastapi import APIRouter

from app.api.routes import (
    catalog,
    customers,
    designs,
    health,
    inventory,
    losses,
    orders,
    payments,
    production,
    quotations,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(catalog.router)
api_router.include_router(customers.router)
api_router.include_router(quotations.router)
api_router.include_router(orders.router)
api_router.include_router(payments.router)
api_router.include_router(inventory.router)
api_router.include_router(designs.router)
api_router.include_router(production.router)
api_router.include_router(losses.router)
