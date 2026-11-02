from fastapi import FastAPI


app = FastAPI(
    title="Smart Budget AI",
    description="API de análise e automação orçamentária.",
    version="0.1.0",
)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}