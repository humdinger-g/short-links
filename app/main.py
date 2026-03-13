from fastapi import FastAPI

from app.api.router import api_router
from app.lifecycle import lifespan
from app.settings import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)
app.include_router(api_router)

