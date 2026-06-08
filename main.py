from fastapi import FastAPI
from dotenv import load_dotenv
from app.api.routes import router

load_dotenv()

app = FastAPI(
    title="QueryPal",
    description="Natural language to SQL using LLMs",
    version="1.0.0"
)

app.include_router(router)