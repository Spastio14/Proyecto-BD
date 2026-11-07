from fastapi import APIRouter

from app.api.routes import (
    auth,
    catalog,
    customers,
    deliveries,
    designs,
    employees,
    health,
    inventory,
    losses,
    orders,
    payments,
    production,
    profiles,
    purchases,
    quotations,
    reports,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
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
api_router.include_router(purchases.router)
api_router.include_router(deliveries.router)
api_router.include_router(reports.router)
api_router.include_router(employees.router)
api_router.include_router(profiles.router)
