
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health, chat, sessions, feedback, auth

app = FastAPI(title="AI Chatbot API", version="0.1.0")

# ---- CORS (adjust origins for your frontend) ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # must include Authorization and X-Session-Id
)

# ---- Routers ----
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(feedback.router)
app.include_router(auth.router)

# ---- Root redirect ----
@app.get("/")
def root():
    return {"status": "ok", "message": "AI Chatbot backend is running"}
