#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
免费去广告 - iOS 描述文件生成器（不需要任何 App）

生成两种描述文件：
  1. clean-dns.mobileconfig        明文 DNS 指向 AdGuard 广告过滤 DNS（国内 53 端口实测可达）
  2. clean-dns-doh.mobileconfig    加密 DoH 版，指向你自己的过滤解析器（需要自建，见 doh/）

用法：
  python make_profile.py
  python make_profile.py --doh https://dns.example.com/dns-query --ip 1.2.3.4
"""
import argparse
import plistlib
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "dist"


def build(display_name: str, identifier: str, dns_settings: dict, desc: str) -> bytes:
    payload_uuid = str(uuid.uuid4()).upper()
    profile = {
        "PayloadContent": [
            {
                "PayloadType": "com.apple.dnsSettings.managed",
                "PayloadIdentifier": f"{identifier}.dnssettings",
                "PayloadUUID": payload_uuid,
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
    ap.add_argument("--doh", default="", help="DoH 地址，例如 https://dns.example.com/dns-query")
    ap.add_argument("--ip", default="", help="DoH 服务器 IP（可选，用于加速/防污染）")
    a = ap.parse_args()

    OUT.mkdir(exist_ok=True)

    # 方案 1：明文 DNS（AdGuard 广告过滤 DNS，国内直连可达）
    plain = {
        "ServerAddresses": ["94.140.14.14", "94.140.15.15"],
    }
    p1 = OUT / "clean-dns.mobileconfig"
    p1.write_bytes(
        build(
            "免费去广告·DNS 过滤",
            "com.freeadblock.dns.plain",
            plain,
            "把系统 DNS 指向带广告过滤的解析器，全系统拦截广告/追踪域名。不装任何 App，可随时删除。",
        )
    )

    # 方案 2：DoH（需自建过滤解析器，doh/ 目录里有现成代码）
    if a.doh:
        doh = {"DNSProtocol": "HTTPS", "ServerURL": a.doh}
        if a.ip:
            doh["ServerAddresses"] = [x.strip() for x in a.ip.split(",") if x.strip()]
        p2 = OUT / "clean-dns-doh.mobileconfig"
        p2.write_bytes(
            build(
                "免费去广告·DoH 加密过滤",
                "com.freeadblock.dns.doh",
                doh,
                "使用你自己部署的 DoH 过滤解析器，查询全程加密，规则完全由你决定。",
            )
        )
        print(f"OK  {p2.name}  -> {a.doh}")
    else:
        print("跳过 DoH 描述文件（未传 --doh，需要自建解析器时再加）")

    print(f"OK  {p1.name}  -> 94.140.14.14 / 94.140.15.15")

    # 自检：能重新解析回来，字段齐全
    for f in OUT.glob("*.mobileconfig"):
        with open(f, "rb") as fh:
            d = plistlib.load(fh)
        assert d["PayloadType"] == "Configuration"
        s = d["PayloadContent"][0]["DNSSettings"]
        assert s, f"{f.name} 缺少 DNSSettings"
        print(f"    校验通过 {f.name}  ({f.stat().st_size} B)  {s}")


if __name__ == "__main__":
    main()
