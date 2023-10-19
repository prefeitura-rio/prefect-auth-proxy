# -*- coding: utf-8 -*-
from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
    ALTER TABLE "user"
    ADD COLUMN "is_admin" BOOLEAN DEFAULT FALSE;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
    ALTER TABLE "user"
    DROP COLUMN "is_admin";
    """
