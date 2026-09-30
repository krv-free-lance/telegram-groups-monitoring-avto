"""Optional proxy settings for Telethon (userbot) and aiogram (bot)."""
from urllib.parse import urlparse

from telethon import connection


def telethon_proxy_kwargs(proxy_url: str | None, mtproxy: str | None) -> dict:
    """Build TelegramClient kwargs.

    proxy_url: socks5://user:pass@host:port or http://host:port
    mtproxy:   host:port:secret
    """
    if mtproxy:
        host, port, secret = mtproxy.rsplit(":", 2)
        return {
            "connection": connection.ConnectionTcpMTProxyRandomizedIntermediate,
            "proxy": (host, int(port), secret),
        }
    if proxy_url:
        u = urlparse(proxy_url)
        return {
            "proxy": {
                "proxy_type": u.scheme,
                "addr": u.hostname,
                "port": u.port,
                "username": u.username,
                "password": u.password,
                "rdns": True,
            }
        }
    return {}
