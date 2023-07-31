# -*- coding: utf-8 -*-
import pytest
from httpx import AsyncClient

from app.models import User

from .conftest import PASSWORD, USERNAME


@pytest.mark.anyio
async def test_auth_login_success(client: AsyncClient, create_user: User):
    # Login success
    response = await client.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert response.status_code == 200
    assert response.json() == {"token": str(create_user.token), "success": True}


@pytest.mark.anyio
async def test_auth_login_wrong_password(client: AsyncClient):
    # Wrong password
    response = await client.post(
        "/auth/login",
        json={"username": "test_username", "password": "wrong_password"},
    )
    assert response.status_code == 200
    assert response.json() == {"token": "", "success": False}


@pytest.mark.anyio
async def test_auth_login_non_existent_user(client: AsyncClient):
    # Non-existent user
    response = await client.post(
        "/auth/login",
        json={"username": "non_existent_username", "password": "wrong_password"},
    )
    assert response.status_code == 200
    assert response.json() == {"token": "", "success": False}
