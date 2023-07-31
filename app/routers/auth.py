# -*- coding: utf-8 -*-
from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel

from app.models import User
from app.utils import password_verify

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    success: bool


@router.post("/login")
async def login(data: LoginRequest) -> LoginResponse:
    logger.info(f"Login attempt for {data.username}")
    user = await User.filter(username=data.username).first()
    logger.debug(f"User: {user}")
    if not user:
        return LoginResponse(token="", success=False)
    if not password_verify(data.password, user.password):
        return LoginResponse(token="", success=False)
    return LoginResponse(token=str(user.token), success=True)
