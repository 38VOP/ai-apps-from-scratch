from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db, PREVIEWS_DIR
from routers import sources, categories, models, cart, projects, admin

app = FastAPI(title="3D Model Telegram Aggregator API v1.2.0", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/previews", StaticFiles(directory=PREVIEWS_DIR), name="previews")


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(sources.router)
app.include_router(categories.router)
app.include_router(models.router)
app.include_router(cart.router)
app.include_router(projects.router)
app.include_router(admin.router)
