# -*- coding: utf-8 -*-
from . import getenv_or_action
from .base import *  # noqa: F401, F403

# Database configuration
DATABASE_URL = getenv_or_action("DATABASE_URL", action="raise")

# Password hashing configuration
if getenv_or_action("PASSWORD_HASH_ALGORITHM", action="ignore"):
    PASSWORD_HASH_ALGORITHM = getenv_or_action("PASSWORD_HASH_ALGORITHM")
if getenv_or_action("PASSWORD_HASH_NUMBER_OF_ITERATIONS", action="ignore"):
    PASSWORD_HASH_NUMBER_OF_ITERATIONS = int(getenv_or_action("PASSWORD_HASH_NUMBER_OF_ITERATIONS"))

# Timezone configuration
if getenv_or_action("TIMEZONE", action="ignore"):
    TIMEZONE = getenv_or_action("TIMEZONE")

# Prefect API configuration
PREFECT_API_URL = getenv_or_action("PREFECT_API_URL", action="raise")
