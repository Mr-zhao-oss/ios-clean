#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实测验证：把 dist/sing-box.json 跑起来，逐条 A/B 对比
  A. 不走代理  —— 真实可达的域名应该 200
  B. 走代理    —— 命中广告规则的域名应该被丢弃（5xx / 连接失败）
用法：
  python verify/run_test.py D:\\path\\to\\sing-box.exe
"""
import json
import pathlib
import subprocess
import sys
import time

CFG = pathlib.Path("dist/sing-box.json")
OUT = pathlib.Path("verify/test-singbox.json")

# (url, 说明, 期望是否被拦)
TESTS = [
    ("https://www.baidu.com/", "正常站点", False),
    ("https://www.bing.com/", "正常站点", False),
    ("https://applovin.com/", "广告平台官网", True),
    ("https://pangle.io/", "穿山甲", True),
    ("https://www.doubleclick.net/", "Google 双击", True),
]


def build():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    cfg["inbounds"] = [
        {"type": "mixed", "tag": "test-in", "listen": "127.0.0.1", "listen_port": 7899}
    ]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(cfg["route"]["rules"][0]["domain_suffix"])


def curl(url, proxy=None):
    cmd = ["curl", "-s", "-o", "NUL", "-w", "%{http_code}", "--max-time", "12",
           "-A", "Mozilla/5.0", url]
    if proxy:
        cmd[-1:-1] = ["-x", proxy]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        code = int((r.stdout or "0").strip())
    except ValueError:
        code = 0
    return code, r.returncode


def is_blocked(code, rc):
    # sing-box 拒绝时回 502；连接被丢弃时 curl 直接失败（rc!=0 / code=0）
    return rc != 0 or code == 0 or code >= 500


def main():
    n = build()
    print(f"测试配置 {OUT}，规则 {n} 条\n")

    exe = sys.argv[1] if len(sys.argv) > 1 else "sing-box"
    proc = subprocess.Popen([exe, "run", "-c", str(OUT)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(2.5)
    if proc.poll() is not None:
        print("sing-box 启动失败：")
        print(proc.stdout.read().decode("utf-8", "ignore")[:800])
        return 1

    passed = 0
    for url, label, should_block in TESTS:
        direct_code, _ = curl(url)
        p_code, p_rc = curl(url, "http://127.0.0.1:7899")
        blocked = is_blocked(p_code, p_rc)

        if should_block:
            ok = blocked
        else:
            # 正常站点：直连能通，走代理也必须能通
            ok = not blocked and direct_code > 0

        passed += ok
        print(f"  {'PASS' if ok else 'FAIL'}  {label:<10} {url:<32} "
              f"直连={direct_code:<4} 代理={p_code:<4} 判定={'已拦' if blocked else '放行'}")

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    print(f"\n实测 {passed}/{len(TESTS)} 通过")
    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    sys.exit(main())
