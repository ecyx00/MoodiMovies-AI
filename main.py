# TODO: Ensure Pydantic models in app/schemas/ or app/api/models.py
#       are updated according to the v1.2 API specification before implementing endpoints.

from fastapi import FastAPI
from loguru import logger

# Router importları
from app.api.routers import personality, recommendation, webhooks

app = FastAPI(
    title="MoodieMovies AI Service",
    description="API for personality analysis and film recommendations based on personality profiles",
    version="1.2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Router'ları uygulamaya dahil et
logger.info("Registering API routers...")
app.include_router(personality.router)
app.include_router(recommendation.router)
app.include_router(webhooks.router)

@app.on_event("startup")
async def startup_event():
    logger.info("MoodieMovies AI Service starting up")
    
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("MoodieMovies AI Service shutting down")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
