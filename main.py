from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from app.api.routes import router

load_dotenv()

app = FastAPI(
    title="QueryPal",
    description="Natural language to SQL using LLMs",
    version="1.0.0"
)

app.include_router(router)

# Static frontend — mounted after the API router so /query, /schema, and
# /upload are matched first; anything else (/, /app.js, /style.css) falls
# through to the static files here.
app.mount("/", StaticFiles(directory="web", html=True), name="web")