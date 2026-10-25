#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查线上页面：所有相对链接都能打开，描述文件内容正确，配置可被解析。"""
import json
import re
import sys
import urllib.request
from pathlib import Path

BASE = "https://mr-zhao-oss.github.io/ios-clean/"
UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.headers.get("content-type", ""), r.read()


def main():
    fails = 0
    status, ctype, body = get(BASE)
    html = body.decode("utf-8", "ignore")
    print(f"页面 {status} {ctype} {len(body)}B  title={re.search(r'<title>(.*?)</title>', html).group(1)}")

    links = sorted(set(re.findall(r'href="([^"#][^"]*)"', html)))
    for link in links:
        url = link if link.startswith("http") else BASE + link.lstrip("/")
        try:
            s, t, b = get(url)
            ok = s == 200
            print(f"  {'OK ' if ok else 'BAD'} {s} {len(b):>7}B  {t:<28} {link}")
            fails += 0 if ok else 1
            if link.endswith(".mobileconfig"):
                txt = b.decode("utf-8")
                assert "com.apple.dnsSettings.managed" in txt, "缺 dnsSettings payload"
                assert "94.140.14.14" in txt, "缺 DNS 地址"
                print("      └ 描述文件内容校验通过")
            if link.endswith(".json"):
                json.loads(b)
                print("      └ JSON 合法")
            if link.endswith(".yaml"):
                assert "rules:" in b.decode("utf-8")
                print("      └ YAML 结构存在")
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"  BAD {link} -> {e}")

    # 检查自检页
    s2, _, b2 = get(BASE + "check.html")
    print(f"\n自检页 {s2} {len(b2)}B")
    assert s2 == 200 and b"doubleclick.net" in b2

    print(f"\n{'全部通过' if fails == 0 else f'{fails} 个链接有问题'}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
