# -*- coding: utf-8 -*-
import socket

from . import getenv_or_action

# Logging
LOG_LEVEL = getenv_or_action("LOG_LEVEL", default="INFO")

# Password hashing configuration
PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_NUMBER_OF_ITERATIONS = 60000

# Timezone configuration
TIMEZONE = "America/Sao_Paulo"

# Sentry
SENTRY_ENABLE = False
SENTRY_DSN = None
SENTRY_ENVIRONMENT = None

# Cache
CACHE_ENABLE = getenv_or_action("CACHE_ENABLE", default="false").lower() == "true"
if CACHE_ENABLE:
    CACHE_REDIS_HOST = getenv_or_action("CACHE_REDIS_HOST", action="raise")
    CACHE_REDIS_PORT = int(getenv_or_action("CACHE_REDIS_PORT", action="raise"))
    CACHE_REDIS_PASSWORD = getenv_or_action("CACHE_REDIS_PASSWORD", action="raise")
    CACHE_REDIS_DB = int(getenv_or_action("CACHE_REDIS_DB", action="raise"))
else:
    CACHE_REDIS_HOST = None
    CACHE_REDIS_PORT = None
    CACHE_REDIS_PASSWORD = None
    CACHE_REDIS_DB = None
CACHE_DEFAULT_TIMEOUT = int(getenv_or_action("CACHE_DEFAULT_TIMEOUT", default="43200"))  # 12 hours

# Profiling
PROFILING_ENABLED = getenv_or_action("PROFILING_ENABLED", default="false") in [
    "true",
    "True",
    "TRUE",
]

# Host
HOST = socket.gethostname()

# Requests timeout
REQUESTS_DEFAULT_TIMEOUT = int(getenv_or_action("REQUESTS_DEFAULT_TIMEOUT", default="30"))
