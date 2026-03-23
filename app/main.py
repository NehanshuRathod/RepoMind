from fastapi import FastAPI
from app.api.health import router as health_router
from app.indexing.index_controller import router as index_router

app = FastAPI(title="REPOMIND API")

app.include_router(index_router)
app.include_router(health_router)

@app.get("/")
def root():
    return{"message" : "API is okay"}