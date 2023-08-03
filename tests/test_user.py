# -*- coding: utf-8 -*-
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models import User
from app.utils import password_verify


@pytest.mark.anyio
@pytest.mark.run(order=1)
async def test_user_create(client: AsyncClient, create_user: User):
    response = await client.post(
        "/user/",
        json={
            "username": "another_username",
            "password": "another_password",
            "is_active": True,
            "token": str(uuid4()),
            "token_expiry": None,
            "scopes": "*",
        },
        headers={"Authorization": f"Bearer {str(create_user.token)}"},
    )
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["username"] == "another_username"
    assert await password_verify("another_password", response_data["password"])
    assert response_data["is_active"]
    assert response_data["token"] is not None
    assert response_data["token_expiry"] is None
    assert response_data["scopes"] == "*"


@pytest.mark.anyio
@pytest.mark.run(order=2)
async def test_user_patch(client: AsyncClient, create_user: User):
    before_user = await User.get(id=create_user.id)
    response = await client.patch(
        f"/user/{create_user.id}",
        json={
            "password": "another_password2",
        },
        headers={"Authorization": f"Bearer {str(create_user.token)}"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["username"] == "test_username"
    after_user = await User.get(id=create_user.id)
    assert await password_verify("another_password2", after_user.password)
    assert response_data["is_active"]
    assert before_user.token == after_user.token
    assert response_data["token_expiry"] is None
    assert response_data["scopes"] == "*"


@pytest.mark.anyio
@pytest.mark.run(order=3)
async def test_user_delete(client: AsyncClient, create_user: User):
    response = await client.delete(
        f"/user/{create_user.id}",
        headers={"Authorization": f"Bearer {str(create_user.token)}"},
    )
    assert response.status_code == 200
    assert response.json()["success"]
