# -*- coding: utf-8 -*-
from app import config

TORTOISE_ORM = {
    "connections": {"default": config.DATABASE_URL},
    "apps": {
        "auth_proxy": {
            "models": [
                "aerich.models",
                "app.models",
            ],
            "default_connection": "default",
        },
    },
}
