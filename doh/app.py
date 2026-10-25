#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
免费去广告 · 自建 DoH 过滤解析器（阿里云函数计算 / 任意 WSGI 服务器）

两种跑法：

A. 本地验证（现在就能跑，用来确认逻辑正确）
     python doh/app.py
     # 另开一个窗口：
     python doh/app.py --test

B. 云端部署（手机在外面也能用，免费额度足够个人）
     阿里云函数计算 FC 3.0 → 创建函数 → Python 3.9 → HTTP 函数 → 代码上传本目录
     默认域名即可用 https://<你的>.cn-hangzhou.fcapp.run/dns-query
     然后：python make_profile.py --doh https://<你的>.cn-hangzhou.fcapp.run/dns-query

配 iOS：生成的 clean-dns-doh.mobileconfig 用 Safari 打开安装即可。
"""
import base64
import json
import socket
import struct
import sys
import urllib.request

UPSTREAM = "https://doh.pub/dns-query"

BLOCK = [
    "doubleclick.net", "googlesyndication.com", "googleadservices.com",
    "applovin.com", "unityads.unity3d.com", "inmobi.com", "chartboost.com",
    "vungle.com", "mintegral.com", "adcolony.com", "moloco.com", "ironsrc.com",
    "tapjoy.com", "appnext.com", "liftoff.io", "amazon-adsystem.com",
    "pangolin-sdk-toutiao.com", "pangolin-sdk-toutiao-b.com", "pglstatp-toutiao.com",
    "pangle.io", "pangle-sg.com", "gdt.qq.com", "pgdt.gtimg.cn",
    "ad.kuaishou.com", "adstatic.kuaishou.com", "mobads.baidu.com",
    "tanx.com", "alimama.com", "adx.jd.com", "show.jd.com",
    "ssp.sina.com.cn", "cm.bilibili.com", "miaozhen.com", "admaster.com.cn",
    "adnxs.com", "rubiconproject.com", "pubmatic.com", "openx.net",
    "criteo.com", "taboola.com", "outbrain.com", "moatads.com",
]


def parse_question(msg: bytes):
    """返回 (qname, question_end_offset)"""
    off, labels = 12, []
    while off < len(msg):
        n = msg[off]
        if n == 0:
            off += 1
            break
        if n & 0xC0:
            off += 2
            break
        labels.append(msg[off + 1: off + 1 + n].decode("latin-1"))
        off += 1 + n
    off += 4  # qtype + qclass
    return ".".join(labels).lower(), off


def is_blocked(name: str) -> bool:
    return any(name == d or name.endswith("." + d) for d in BLOCK)


def nxdomain(msg: bytes, qend: int) -> bytes:
    out = bytearray(msg[:qend])
    out[2:4] = struct.pack("!H", 0x8183)  # QR=1 RD=1 RA=1 RCODE=3
    out[6:12] = b"\x00" * 6
    return bytes(out)


def handle(query: bytes) -> bytes:
    if len(query) < 17:
        raise ValueError("bad query")
    name, qend = parse_question(query)
    if is_blocked(name):
        return nxdomain(query, qend)
    req = urllib.request.Request(
        UPSTREAM,
        data=query,
        headers={"content-type": "application/dns-message", "accept": "application/dns-message"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.read()


# ---------------- WSGI（阿里云函数计算 HTTP 函数 / 本地 gunicorn 均可） ----------------
def handler(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    if method == "POST":
        length = int(environ.get("CONTENT_LENGTH") or 0)
        query = environ["wsgi.input"].read(length)
    else:
        qs = environ.get("QUERY_STRING", "")
        dns = ""
        for part in qs.split("&"):
            if part.startswith("dns="):
                dns = part[4:]
                break
        if not dns:
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"adblock DoH ready"]
        dns = dns.replace("-", "+").replace("_", "/")
        query = base64.b64decode(dns + "=" * (-len(dns) % 4))

    try:
        resp = handle(query)
    except Exception as e:  # noqa: BLE001
        start_response("502 Bad Gateway", [("Content-Type", "text/plain")])
        return [f"upstream error: {e}".encode()]

    start_response("200 OK", [
        ("Content-Type", "application/dns-message"),
        ("Cache-Control", "max-age=60"),
    ])
    return [resp]


# ---------------- 本地跑 + 自测 ----------------
def build_query(name: str, qtype: int = 1) -> bytes:
    tid = b"\x12\x34"
    flags = struct.pack("!H", 0x0100)
    q = struct.pack("!H", 1) + b"\x00" * 6
    body = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"
    return tid + flags + q + body + struct.pack("!HH", qtype, 1)


def self_test():
    ok = 0
    cases = [
        ("doubleclick.net", True),
        ("pangle.io", True),
        ("gdt.qq.com", True),
        ("www.qq.com", False),
        ("www.baidu.com", False),
    ]
    for name, should_block in cases:
        r = handle(build_query(name))
        rcode = r[3] & 0x0F
        blocked = rcode == 3
        good = blocked == should_block
        ok += good
        print(f"  {'PASS' if good else 'FAIL'}  {name:<22} rcode={rcode} "
              f"{'NXDOMAIN(已拦)' if blocked else '正常解析'}")
    print(f"\n自测: {ok}/{len(cases)} 通过")
    return ok == len(cases)


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(0 if self_test() else 1)
    from wsgiref.simple_server import make_server
    port = 8053
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    print(f"本地 DoH 已启动: http://127.0.0.1:{port}/dns-query")
    make_server("127.0.0.1", port, handler).serve_forever()
