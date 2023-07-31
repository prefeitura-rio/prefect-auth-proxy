# -*- coding: utf-8 -*-
from typing import Annotated

import pendulum
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

from app import config
from app.models import User


async def validate_token(token: Annotated[str, Depends(HTTPBearer())]):
    token = token.credentials
    user: User = await User.get_or_none(token=token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    if user.token_expiry and user.token_expiry < pendulum.now(tz=config.TIMEZONE):
        raise HTTPException(status_code=401, detail="Expired token")
