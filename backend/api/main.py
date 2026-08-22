# api/main.py
# S.P.A.R.K. FastAPI application entry point

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from api.core.config import settings
from api.core.redis_client import limiter
from api.routers.auth import router as auth_router

app = FastAPI(
    title=settings.PROJECT_NAME, version="2.0.0", docs_url="/docs", redoc_url="/redoc"
)

# Attach SlowAPI rate limiter state and middleware
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please wait before retrying."},
    )


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": "2.0.0",
        "status": "online",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
