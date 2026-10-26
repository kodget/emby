"""Reuse Celery's Redis broker for startup checks and the Beat leadership lease."""
import ipaddress
from urllib.parse import urlsplit


class RuntimeConfigurationError(ValueError):
    """A predefined, credential-free configuration diagnostic."""


def validate_broker_url(url):
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower()
        valid = parsed.scheme in ('redis', 'rediss') and host and parsed.port != 0
        loopback = host == 'localhost' or host.endswith('.localhost')
        try:
            address = ipaddress.ip_address(host)
            loopback |= address.is_loopback or address.is_unspecified
        except ValueError:
            pass
        if not valid or loopback:
            raise ValueError
    except (TypeError, ValueError):
        raise RuntimeConfigurationError('Combined startup requires an existing remote redis:// or rediss:// Celery broker.') from None
    return url


def broker_client(app):
    from redis import Redis, SSLConnection
    url = validate_broker_url(app.conf.broker_url)
    ssl = app.conf.broker_use_ssl
    options = dict(ssl) if isinstance(ssl, dict) else {}
    if ssl and urlsplit(url).scheme == 'redis':
        options['connection_class'] = SSLConnection
    options.update(socket_connect_timeout=5, socket_timeout=5)
    return Redis.from_url(url, **options)
