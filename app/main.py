# -*- coding: utf-8 -*-
from fastapi import FastAPI
from tortoise.contrib.fastapi import register_tortoise

from app.db import TORTOISE_ORM
from app.routers import auth, proxy, user

app = FastAPI()

app.include_router(auth.router)
app.include_router(proxy.router)
app.include_router(user.router)

register_tortoise(
    app,
    config=TORTOISE_ORM,
    generate_schemas=False,
    add_exception_handlers=True,
)
