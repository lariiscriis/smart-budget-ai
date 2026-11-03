from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.categories import router as categories_router
from app.routers.budgets import router as budgets_router
from app.routers.dashboard import router as dashboard_router
from app.routers.expenses import router as expenses_router
from app.routers.imports import router as imports_router

app = FastAPI(
    title="Smart Budget AI",
    description="API de análise e automação orçamentária.",
    version="0.1.0",
)

allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


app.include_router(categories_router)
app.include_router(budgets_router)
app.include_router(expenses_router)
app.include_router(dashboard_router)
app.include_router(imports_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}