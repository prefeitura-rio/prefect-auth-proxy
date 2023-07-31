# -*- coding: utf-8 -*-
from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS "tenant" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "slug" VARCHAR(100) NOT NULL UNIQUE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
