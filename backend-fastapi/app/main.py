from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.models.database import init_db
from app.routers import documents, verify, applications


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings.ensure_dirs()
    await init_db()
    yield
    # Shutdown (nothing to clean up for local dev)


app = FastAPI(
    title="IDP AI Service",
    description="Intelligent Document Processing — AI verification service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in UAT
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/documents", tags=["Documents"])
app.include_router(verify.router, prefix="/verify", tags=["Verification"])
app.include_router(applications.router, prefix="/applications", tags=["Applications"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "IDP AI Service", "version": "1.0.0"}
