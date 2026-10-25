# iOS 免费去广告（Jinx 的免费替代）

视频 [BV1Q8Nd6ZEsN](https://www.bilibili.com/video/BV1Q8Nd6ZEsN) 里的 iOS 方案是 **Jinx**：免费试用 14 天，之后 **3 元/月 或 24 元买断**。它的做法是两步——

1. **DNS 保护**：装一个 VPN 配置，把系统 DNS 换成自己的过滤解析器
2. **HTTPS 深度拦截**：装一张根证书做中间人，解密流量后按规则改包

这个项目把第 1 步用**完全免费**的方式做出来；第 2 步（装证书中间人）**不建议做**，理由见最后一节。

---

## 一分钟版（什么都不用装）

用 Safari 打开：**https://mr-zhao-oss.github.io/ios-clean/**

点「下载描述文件」→ 允许 → 设置 → 已下载的描述文件 → 安装。完。

卸载：设置 → 通用 → VPN 与设备管理 → 删除。

**原理**：系统 DNS 指向带广告过滤的解析器（AdGuard DNS，`94.140.14.14`）。广告 SDK 去解析广告域名时拿到 `0.0.0.0`，请求发不出去，开屏/插屏加载失败。

**实测数据**（本项目实测，非推测）：

| 检查项 | 结果 |
|---|---|
| `94.140.14.14:53` 国内直连 | ✅ 通，197ms，未被劫持 |
| `doubleclick.net` / `pagead2.googlesyndication.com` | ✅ 返回 `0.0.0.0` |
| `applovin.com` / `pangle.io` / `gdt.qq.com` | ✅ 被拦 |
| `www.baidu.com` / `www.qq.com` | ✅ 正常解析，未误伤 |
| DoH（443）/ DoT（853）到境外解析器 | ❌ 全部超时——所以只能用明文 53 |

---

## 规则表版（更彻底，推荐）

公共 DNS 的过滤列表对**国内**广告域名覆盖不全（实测 `ad.toutiao.com` 就没被拦）。想自己掌控，用免费开源的 **Karing**（App Store 免费，兼用 Clash 配置）或 **sing-box**，导入本项目生成的配置：

| 文件 | 给谁用 |
|---|---|
| `dist/clash.yaml` | Karing / Clash / Stash / ClashX |
| `dist/sing-box.json` | sing-box / SFI / Hiddify |
| `dist/hosts.txt` | AdGuard Home / 路由器 / 电脑 |
| `dist/domains.txt` | 纯清单，自己拿去用 |

配置特点：**全部流量直连**（不需要任何机场、节点、订阅），只把广告域名 `REJECT` 掉；DNS 上游走国内可达的 `doh.pub` 和 `dns.alidns.com`。

改规则：编辑 `rules/ads-core.txt`，一行一个域名，然后 `python build.py` 重新生成。

**实测数据**（`verify/run_test.py`，用 sing-box 1.14.4 起代理做 A/B 对比）：

```
PASS  正常站点    https://www.baidu.com/   直连=200 代理=200 判定=放行
PASS  正常站点    https://www.bing.com/    直连=302 代理=302 判定=放行
PASS  广告平台    https://applovin.com/    直连=307 代理=0   判定=已拦
PASS  穿山甲      https://pangle.io/       直连=0   代理=0   判定=已拦
PASS  Google双击  https://www.doubleclick.net/ 直连=0 代理=0 判定=已拦
实测 5/5 通过
```

---

## 自建加密 DoH（不想把 DNS 查询交给第三方时）

`doh/worker.js`（Cloudflare Workers，免费 10 万次/天）和 `doh/app.py`（阿里云函数计算 / 任意 WSGI，免费额度够个人用）各一份实现：命中广告域名回 `NXDOMAIN`，其余转发 `doh.pub`。

本地先跑一遍自测（不用任何账号）：

```bash
python doh/app.py --test
# PASS doubleclick.net  rcode=3 NXDOMAIN(已拦)
# PASS www.qq.com       rcode=0 正常解析
# 自测: 5/5 通过
```

部署好后生成对应的描述文件：

```bash
python make_profile.py --doh https://你的域名/dns-query
# → dist/clean-dns-doh.mobileconfig
```

> Cloudflare 的 `*.workers.dev` 在大陆基本不通，必须绑自己的域名。

---

## 为什么不做「装证书深度拦截」

Jinx 收费的核心卖点是 HTTPS 中间人。它要求你：

1. 把一张**根证书**装进手机并设为完全信任
2. 让某个 App 的 VPN 接管**全部**加密流量

等价于把这个 App 的开发者变成你和每个网站之间的中间人。它能改广告，也能改登录页、能看到明文密码、能注入任何内容。一个 24 元买断的软件，不值得赌这个。而且 iOS 上动私有 API 的中间人方案，随时可能被系统更新打断。

**DNS 层拦不到的部分**（抖音、淘宝、微博这类走 IP 直连 / 私有 HTTPDNS 的大厂开屏广告），承认拦不到，比装张证书假装能拦要诚实。

---

## 还能免费做的（视频后半段那些）

- 设置 → 隐私与安全性 → 跟踪 → 关闭「允许 App 请求跟踪」
- 设置 → 隐私与安全性 → Apple 广告 → 关闭个性化广告
- 微信 → 我 → 设置 → 个人信息与权限 → 个性化广告管理 → 关闭
- 各 App 内「个性化推荐」逐个关闭（抖音、淘宝、微博都在设置里）
- 主屏图标上的小红点广告：长按图标 → 关闭角标

---

## 文件结构

```
build.py                规则 → 配置生成器
make_profile.py         生成 iOS 描述文件
rules/ads-core.txt      广告域名清单（保守档，105 条）
doh/worker.js           Cloudflare Workers DoH
doh/app.py              阿里云函数计算 / 本地 DoH
verify/run_test.py      A/B 实测脚本
dist/                   生成产物
index.html              手机端安装页
check.html              装完自检页
```

## 许可

随便用。规则清单欢迎自己加。
