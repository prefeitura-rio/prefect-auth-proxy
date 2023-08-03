# -*- coding: utf-8 -*-
from uuid import uuid4

from tortoise import Tortoise, run_async

from app.db import TORTOISE_ORM
from app.models import Tenant, User
from app.utils import password_hash


async def run():
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()

    admin_user = await User.create(
        username="admin",
        password=await password_hash("admin"),
        is_active=True,
        token=uuid4(),
        scopes="*",
    )
    tenant1 = await Tenant.create(id="83e06ea4-e7ce-46f1-8bb9-d9bc9ba11f1f", slug="default")
    tenant2 = await Tenant.create(id="82a6339c-7e31-425e-b489-ecf56da49d71", slug="another")
    await admin_user.tenants.add(tenant1, tenant2)
    await Tortoise.close_connections()


if __name__ == "__main__":
    run_async(run())
