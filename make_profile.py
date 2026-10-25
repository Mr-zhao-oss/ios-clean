#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
免费去广告 - iOS 描述文件生成器

⚠️ 限制（实测得出的结论，别绕）：
   苹果的 com.apple.dnsSettings.managed 载荷里 DNSProtocol 是**必填**字段，
   只支持加密 DNS（HTTPS / TLS），不支持「直接填一个明文 DNS 服务器」。
   而境外 DoH(443) / DoT(853) 在国内全部超时，所以这条路必须有自己的解析器。

   没有服务器？用 Wi-Fi 里手动改 DNS 的办法（index.html 方案 1），一样免费。

用法：
  python make_profile.py --doh https://dns.example.com/dns-query
  python make_profile.py --doh https://dns.example.com/dns-query --ip 1.2.3.4
  python make_profile.py --dot dns.example.com --ip 1.2.3.4
"""
import argparse
import plistlib
import sys
import uuid
from pathlib import Path

OUT = Path(__file__).resolve().parent / "dist"


def build(display_name: str, identifier: str, dns_settings: dict, desc: str) -> bytes:
    profile = {
        "PayloadContent": [
            {
                "PayloadType": "com.apple.dnsSettings.managed",
                "PayloadIdentifier": f"{identifier}.dnssettings",
                "PayloadUUID": str(uuid.uuid4()).upper(),
                "PayloadVersion": 1,
                "PayloadDisplayName": display_name,
                "PayloadDescription": desc,
                "DNSSettings": dns_settings,
            }
        ],
        "PayloadType": "Configuration",
        "PayloadIdentifier": identifier,
        "PayloadUUID": str(uuid.uuid4()).upper(),
        "PayloadVersion": 1,
        "PayloadDisplayName": display_name,
        "PayloadDescription": desc,
        "PayloadOrganization": "free-adblock",
        "PayloadRemovalDisallowed": False,
    }
    return plistlib.dumps(profile, fmt=plistlib.FMT_XML, sort_keys=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doh", default="", help="DoH 地址，如 https://dns.example.com/dns-query")
    ap.add_argument("--dot", default="", help="DoT 主机名，如 dns.example.com")
    ap.add_argument("--ip", default="", help="服务器 IP（可选，逗号分隔，用于免去首跳解析）")
    a = ap.parse_args()

    if not a.doh and not a.dot:
        print("需要 --doh <URL> 或 --dot <主机名>，两者都指向你自己的过滤解析器。")
        print("没有服务器？用 Wi-Fi 手动改 DNS 的方式，见 index.html 方案 1。")
        return 1

    OUT.mkdir(exist_ok=True)
    ips = [x.strip() for x in a.ip.split(",") if x.strip()]

    if a.doh:
        s = {"DNSProtocol": "HTTPS", "ServerURL": a.doh}
        if ips:
            s["ServerAddresses"] = ips
        path = OUT / "clean-dns-doh.mobileconfig"
        payload = build("免费去广告·DoH 加密过滤", "com.freeadblock.dns.doh", s,
                        "使用自建的 DoH 过滤解析器，查询全程加密，规则归你。")
        path.write_bytes(payload)
        print(f"OK  {path}  -> {a.doh}")

    if a.dot:
        s = {"DNSProtocol": "TLS", "ServerName": a.dot}
        if ips:
            s["ServerAddresses"] = ips
        path = OUT / "clean-dns-dot.mobileconfig"
        payload = build("免费去广告·DoT 加密过滤", "com.freeadblock.dns.dot", s,
                        "使用自建的 DoT 过滤解析器，查询全程加密，规则归你。")
        path.write_bytes(payload)
        print(f"OK  {path}  -> {a.dot}")

    # 自检：回读并断言必需字段
    for f in OUT.glob("*.mobileconfig"):
        with open(f, "rb") as fh:
            d = plistlib.load(fh)
        assert d["PayloadType"] == "Configuration"
        s = d["PayloadContent"][0]["DNSSettings"]
        assert s.get("DNSProtocol") in ("HTTPS", "TLS"), "DNSProtocol 必须是 HTTPS 或 TLS"
        if s["DNSProtocol"] == "HTTPS":
            assert s.get("ServerURL"), "DoH 必须带 ServerURL"
        else:
            assert s.get("ServerName"), "DoT 必须带 ServerName"
        print(f"    校验通过 {f.name}  {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
