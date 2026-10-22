from slowapi import Limiter
from slowapi.util import get_remote_address

from src.configs import config


# Global default applies to every route (via SlowAPIMiddleware); costly or side-effecting
# routes add `@limiter.limit(config.rate_limit_strict)`.
limiter = Limiter(key_func=get_remote_address, default_limits=[config.rate_limit_default])
