# -*- coding: utf-8 -*-
import asyncio
from uuid import uuid4

import pytest
from httpx import AsyncClient
from loguru import logger
from tortoise import Tortoise

from app.db import TORTOISE_ORM
from app.main import app
from app.models import User
from app.utils import password_hash

USERNAME = "test_username"
PASSWORD = "test_password"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
async def initialize_tests():
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()
    await User.all().delete()
    logger.info("Tortoise-ORM schemas generated")
    yield
    await Tortoise.close_connections()


@pytest.fixture(scope="module")
async def create_user():
    # Create user
    password_hashed = password_hash(PASSWORD)
    user = await User.create(
        username=USERNAME,
        password=password_hashed,
        is_active=True,
        token=str(uuid4()),
        scopes="*",
    )
    assert await User.filter(username=USERNAME).exists()
    yield user
    await user.delete()
