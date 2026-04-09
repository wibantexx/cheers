from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limit import limiter
from app.api.routes import auth, users, matching, chat, moderation

app = FastAPI(title="Cheers API", version="1.0.0", docs_url="/docs")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://cheers.vercel.app"],
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