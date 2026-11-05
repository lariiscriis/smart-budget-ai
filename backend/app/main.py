from fastapi import FastAPI, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.auth import get_current_user
from app.config import settings
from app.routers.auth import router as auth_router
from app.routers.audit import router as audit_router
from fastapi.middleware.cors import CORSMiddleware
from app.routers.categories import router as categories_router
from app.routers.budgets import router as budgets_router
from app.routers.dashboard import router as dashboard_router
from app.routers.expenses import router as expenses_router
from app.routers.imports import router as imports_router
from app.routers.copilot import router as copilot_router
from app.routers.alerts import router as alerts_router
from app.routers.automations import router as automations_router
from app.routers.campaigns import router as campaigns_router
from app.routers.incomes import router as incomes_router

app = FastAPI(
    title="Smart Budget AI",
    description="API de análise e automação orçamentária.",
    version="0.1.0",
)

allowed_origins = settings.web_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Aurora-Request"],
)


app.include_router(auth_router)
for financial_router in (
    categories_router, budgets_router, expenses_router, dashboard_router,
    imports_router, copilot_router, alerts_router, automations_router,
    campaigns_router, incomes_router, audit_router,
):
    app.include_router(financial_router, dependencies=[Depends(get_current_user)])


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError):
    # Never echo submitted passwords or other request values in validation errors.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(item["loc"]), "type": item["type"], "msg": item["msg"]}
        for item in error.errors()
    ]})


@app.middleware("http")
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
