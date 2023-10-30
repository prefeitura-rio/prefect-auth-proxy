# -*- coding: utf-8 -*-
import socket
from os import getenv

# Password hashing configuration
PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_NUMBER_OF_ITERATIONS = 60000

# Timezone configuration
TIMEZONE = "America/Sao_Paulo"

# Sentry
SENTRY_ENABLE = False
SENTRY_DSN = None
SENTRY_ENVIRONMENT = None

# Profile
PROFILING_ENABLED = getenv("PROFILING_ENABLED", "false") in ["true", "True", "TRUE"]

# Host
HOST = socket.gethostname()
