from fastapi import FastAPI

app = FastAPI(
    title="Smart Document Formatting Agent API",
    description="API to interact with the agentic document formatting system.",
    version="0.1.0"
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Smart Document Formatting Agent API!"}

# Include routers from endpoints.py
from .endpoints import router as api_router
app.include_router(api_router, prefix="/api") # All these routes will be under /api
