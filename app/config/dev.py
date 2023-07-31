# -*- coding: utf-8 -*-
from . import getenv_or_action
from .base import *  # noqa: F401, F403

# Database configuration
DATABASE_URL = getenv_or_action(
    "DATABASE_URL", default="postgres://postgres:postgres@localhost:5432/postgres"
)

# Prefect API configuration
PREFECT_API_URL = getenv_or_action("PREFECT_API_URL", default="http://localhost:4200/graphql")
