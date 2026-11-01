from fastapi import FastAPI

app = FastAPI(
    title="Multicombot API",
    description="A knowledge-bot platform for multiple companies.",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "app": "Multicombot API",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "ok"}