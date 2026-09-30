from telethon import connection

from app.proxy import telethon_proxy_kwargs


def test_no_proxy():
    assert telethon_proxy_kwargs(None, None) == {}


def test_socks():
    p = telethon_proxy_kwargs("socks5://u:p@1.2.3.4:1080", None)["proxy"]
    assert (p["proxy_type"], p["addr"], p["port"], p["username"], p["password"]) == (
        "socks5", "1.2.3.4", 1080, "u", "p")


def test_mtproxy():
    kw = telethon_proxy_kwargs(None, "proxy.example.com:443:ee00ff")
    assert kw["proxy"] == ("proxy.example.com", 443, "ee00ff")
    assert kw["connection"] is connection.ConnectionTcpMTProxyRandomizedIntermediate
