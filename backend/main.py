from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
from knowledge import app as knowledge_router

app = FastAPI(
    title="Multicombot API",
    description="A knowledge-bot platform for multiple companies.",
    version="0.1.0",
)


DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
app.include_router(knowledge_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[v.strip() for v in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if v.strip()],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def root():
    if (DIST / "index.html").is_file():
        return FileResponse(DIST / "index.html")
    return {
        "app": "Multicombot API",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/bot/{slug}", include_in_schema=False)
def bot_page(slug: str):
    return root()
