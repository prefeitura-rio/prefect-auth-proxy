# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from uuid import uuid4

from tortoise import Tortoise, run_async

from app.db import TORTOISE_ORM
from app.models import User
from app.utils import password_hash


async def run(username: str, password: str):
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()

    await User.create(
        username=username,
        password=await password_hash(password),
        is_active=True,
        token=uuid4(),
        scopes="*",
    )
    await Tortoise.close_connections()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--username", type=str, required=True)
    parser.add_argument("--password", type=str, required=True)
    args = parser.parse_args()
    run_async(run(args.username, args.password))
