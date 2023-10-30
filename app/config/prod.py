# -*- coding: utf-8 -*-
from . import getenv_list_or_action, getenv_or_action
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

# CORS configuration
ALLOWED_ORIGINS = getenv_list_or_action("ALLOWED_ORIGINS", action="ignore")
ALLOWED_ORIGINS_REGEX = None
if not ALLOWED_ORIGINS and not ALLOWED_ORIGINS_REGEX:
    raise EnvironmentError("ALLOWED_ORIGINS or ALLOWED_ORIGINS_REGEX must be set.")
ALLOWED_METHODS = getenv_list_or_action("ALLOWED_METHODS", action="raise")
ALLOWED_HEADERS = getenv_list_or_action("ALLOWED_HEADERS", action="raise")
ALLOW_CREDENTIALS = getenv_or_action("ALLOW_CREDENTIALS", action="raise").lower() == "true"

# Sentry
SENTRY_ENABLE = True
SENTRY_DSN = getenv_or_action("SENTRY_DSN", action="raise")
SENTRY_ENVIRONMENT = getenv_or_action("SENTRY_ENVIRONMENT", action="raise")

# Profile
PROFILING_PATH = "/profile"
