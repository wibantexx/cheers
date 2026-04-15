import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import auth, chat, matching, moderation, users
from app.core.rate_limit import limiter

# Expose Swagger UI only outside production so secrets never leak via docs.
_dev = os.getenv("ENVIRONMENT", "production").lower() != "production"
app = FastAPI(
    title="Cheers API",
    version="1.0.0",
    docs_url="/docs" if _dev else None,
    redoc_url="/redoc" if _dev else None,
    openapi_url="/openapi.json" if _dev else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_origins = [
    "https://frontend-wibantexxs-projects.vercel.app",
    "https://frontend-rho-six-45.vercel.app",
]
if _dev:
    _origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # Allow any preview deployment under this team's scope.
    allow_origin_regex=r"https://frontend-[a-z0-9]+-wibantexxs-projects\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(matching.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(moderation.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}