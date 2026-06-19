from fastapi import FastAPI

from db.database import init_db

app = FastAPI()


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/ping")
def ping():
    from sqlalchemy import inspect
    from db.database import engine

    inspector = inspect(engine)

    print(inspector.get_table_names())
    return {"message": "pong"}