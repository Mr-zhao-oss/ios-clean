#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
免费去广告 - 配置生成器
读 rules/*.txt，生成：
  dist/clash.yaml      Clash / mihomo / Karing / Stash / ClashX
  dist/sing-box.json   sing-box / SFI / Karing / Hiddify
  dist/hosts.txt       AdGuard Home / 路由器 / 电脑端可直接用
  dist/domains.txt     纯域名清单
用法：
  python build.py                     # 只用核心规则（保守）
  python build.py --all               # 核心 + 扩展规则
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RULES = ROOT / "rules"
OUT = ROOT / "dist"

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$"
)


def load(*names):
    seen, out, bad = set(), [], []
    for name in names:
        p = RULES / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            d = line.lower().lstrip(".")
            d = d.replace("*.", "").replace("||", "").rstrip("^")
            if d.startswith("http"):
                continue
            if not DOMAIN_RE.match(d):
                bad.append(d)
                continue
            if d not in seen:
                seen.add(d)
                out.append(d)
    if bad:
        print(f"  ! 跳过 {len(bad)} 条无效写法: {bad[:5]}")
    return out


def build_clash(domains):
    lines = [
        "# 免费去广告 / Clash·mihomo·Karing·Stash 通用配置",
        "# 全部流量直连，只把广告域名丢弃（REJECT）。不需要任何机场/节点。",
        f"# 域名数: {len(domains)}",
        "port: 7890",
        "socks-port: 7891",
        "allow-lan: false",
        "mode: rule",
        "log-level: warning",
        "ipv6: false",
        "unified-delay: true",
        "tcp-concurrent: true",
        "find-process-mode: 'off'",
        "global-client-fingerprint: chrome",
        "",
        "dns:",
        "  enable: true",
        "  ipv6: false",
        "  enhanced-mode: fake-ip",
        "  fake-ip-range: 198.18.0.1/16",
        "  fake-ip-filter:",
        "    - '*.lan'",
        "    - '*.local'",
        "    - '+.msftconnecttest.com'",
        "    - '+.msftncsi.com'",
        "    - 'time.*.com'",
        "  default-nameserver:",
        "    - 223.5.5.5",
        "    - 119.29.29.29",
        "  nameserver:",
        "    - https://doh.pub/dns-query",
        "    - https://dns.alidns.com/dns-query",
        "",
        "proxies: []",
        "proxy-groups: []",
        "",
        "rules:",
    ]
    lines += [f"  - DOMAIN-SUFFIX,{d},REJECT" for d in domains]
    lines += ["  - MATCH,DIRECT", ""]
    return "\n".join(lines)


def build_singbox(domains):
    cfg = {
        "log": {"level": "warn", "timestamp": True},
        "dns": {
            "servers": [
                {"type": "udp", "tag": "bootstrap", "server": "223.5.5.5"},
                {"type": "https", "tag": "doh-tx", "server": "doh.pub", "domain_resolver": "bootstrap"},
                {"type": "https", "tag": "doh-ali", "server": "dns.alidns.com", "domain_resolver": "bootstrap"},
            ],
            "rules": [{"domain_suffix": domains, "action": "reject"}],
            "final": "doh-tx",
            "strategy": "ipv4_only",
        },
        "inbounds": [
            {
                "type": "tun",
                "tag": "tun-in",
                "address": ["172.19.0.1/30"],
                "auto_route": True,
                "strict_route": True,
                "stack": "mixed",
                "mtu": 9000,
            }
        ],
        "outbounds": [{"type": "direct", "tag": "direct"}],
        "route": {
            "rules": [{"domain_suffix": domains, "action": "reject"}],
            "final": "direct",
            "auto_detect_interface": True,
            "default_domain_resolver": "bootstrap",
        },
    }
    return json.dumps(cfg, ensure_ascii=False, indent=2)


def build_hosts(domains):
    head = [
        "# 免费去广告 hosts 版（AdGuard Home 用户直接当自定义规则用）",
        f"# 域名数: {len(domains)}",
    ]
    return "\n".join(head + [f"0.0.0.0 {d}" for d in domains]) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="额外并入 rules/ads-extra.txt")
    a = ap.parse_args()

    names = ["ads-core.txt"] + (["ads-extra.txt"] if a.all else [])
    domains = load(*names)
    OUT.mkdir(exist_ok=True)

    (OUT / "clash.yaml").write_text(build_clash(domains), encoding="utf-8")
    (OUT / "sing-box.json").write_text(build_singbox(domains), encoding="utf-8")
    (OUT / "hosts.txt").write_text(build_hosts(domains), encoding="utf-8")
    (OUT / "domains.txt").write_text("\n".join(domains) + "\n", encoding="utf-8")

    print(f"OK  {len(domains)} 个广告域名")
    for f in ("clash.yaml", "sing-box.json", "hosts.txt", "domains.txt"):
        p = OUT / f
        print(f"    {f:<16} {p.stat().st_size:>8} B")


if __name__ == "__main__":
    main()
