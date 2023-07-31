# -*- coding: utf-8 -*-
from typing import Any

import httpx
from fastapi import APIRouter, Body, Depends, Response

from app import config
from app.dependencies import validate_token

router = APIRouter(prefix="/proxy", tags=["proxy"], dependencies=[Depends(validate_token)])


@router.post("/")
async def proxy(body: Any = Body(...)):
    """
    Proxies requests to the Prefect API.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            config.PREFECT_API_URL,
            data=body,
        )
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response.headers,
        media_type=response.headers["content-type"],
    )
