# -*- coding: utf-8 -*-
from . import getenv_or_action

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
    CACHE_REDIS_URL = getenv_or_action("CACHE_REDIS_URL", action="raise")
else:
    CACHE_REDIS_URL = None
CACHE_DEFAULT_TIMEOUT = int(getenv_or_action("CACHE_DEFAULT_TIMEOUT", default="43200"))  # 12 hours
