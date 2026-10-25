# iOS 免费去广告（Jinx 的免费替代）

视频 [BV1Q8Nd6ZEsN](https://www.bilibili.com/video/BV1Q8Nd6ZEsN) 里的 iOS 方案是 **Jinx**：免费试用 14 天，之后 **3 元/月 或 24 元买断**。它做两件事——

1. **DNS 保护**：装一个 VPN 配置，把系统 DNS 换成自己的过滤解析器
2. **HTTPS 深度拦截**：装一张根证书做中间人，解密流量后按规则改包

这个项目把第 1 步用**完全免费**的方式复刻；第 2 步不建议做，理由见最后一节。

在线页面：**https://mr-zhao-oss.github.io/ios-clean/**

---

## 方案 1：Wi-Fi 里直接改 DNS（零成本，30 秒）

设置 → 无线局域网 → 当前 Wi-Fi 的 ⓘ → 配置 DNS → 手动 → 删掉原来的，添加：

```
94.140.14.14     （主）
94.140.15.15     （备）
```

存储 → 开关一次 Wi-Fi → 打开 `check.html` 自检。

**局限**：只对 Wi-Fi 生效。iOS 不允许改蜂窝流量的 DNS（除非装 VPN 类 App 或描述文件）。

**实测数据**（本项目实测，非推测）：

| 检查项 | 结果 |
|---|---|
| `94.140.14.14:53` 国内直连 | ✅ 通，197ms，未被劫持 |
| `doubleclick.net` / `pagead2.googlesyndication.com` | ✅ 返回 `0.0.0.0` |
| `applovin.com` / `pangle.io` / `gdt.qq.com` | ✅ 被拦 |
| `www.baidu.com` / `www.qq.com` / `www.taobao.com` | ✅ 正常解析，未误伤 |

---

## 方案 2：免费 App + 规则表（Wi-Fi 和蜂窝都管）

公共 DNS 的过滤列表对**国内**广告域名覆盖不全（实测 `ad.toutiao.com` 就没被拦）。想自己掌控，用免费开源的 **Karing**（美区 App Store 免费）或 **sing-box**，导入本项目生成的配置：

| 文件 | 给谁用 |
|---|---|
| `dist/clash.yaml` | Karing / Clash / Stash / ClashX |
| `dist/sing-box.json` | sing-box / SFI / Hiddify |
| `dist/hosts.txt` | AdGuard Home / 路由器 / 电脑 |
| `dist/domains.txt` | 纯清单 |

配置特点：**全部流量直连**（不需要任何机场、节点、订阅），只把广告域名 `REJECT`；DNS 上游走国内可达的 `doh.pub` 和 `dns.alidns.com`。

改规则：编辑 `rules/ads-core.txt`，一行一个域名，然后 `python build.py` 重新生成。

**实测数据**（`verify/run_test.py`，用 sing-box 1.14.4 起代理做 A/B 对比）：

```
PASS  正常站点    https://www.baidu.com/        直连=200 代理=200 判定=放行
PASS  正常站点    https://www.bing.com/         直连=302 代理=302 判定=放行
PASS  广告平台    https://applovin.com/         直连=307 代理=0   判定=已拦
PASS  穿山甲      https://pangle.io/            直连=0   代理=0   判定=已拦
PASS  Google双击  https://www.doubleclick.net/  直连=0   代理=0   判定=已拦
实测 5/5 通过
```

---

## 方案 3：自建加密 DoH + 描述文件（全系统，含蜂窝）

> **为什么不能直接给一个现成的描述文件？**
> 苹果 `com.apple.dnsSettings.managed` 里 `DNSProtocol` 是**必填**字段，只支持 DoT / DoH，不支持「填一个明文 DNS」。
> 而境外 DoH(443) / DoT(853) 在国内实测全部超时：AdGuard、Cloudflare、Google、Quad9、OpenDNS、ControlD、DNS0、LibreDNS、DNSWarden —— 一个都不通。
> 所以这条路必须有**你自己的**解析器，给别人的地址等于给你一堆连不上的东西。

`doh/worker.js`（Cloudflare Workers，免费 10 万次/天）和 `doh/app.py`（阿里云函数计算 / 任意 WSGI，免费额度够个人用）各一份实现：命中广告域名回 `NXDOMAIN`，其余转发 `doh.pub`。

本地先跑一遍自测（不需要任何账号）：

```bash
python doh/app.py --test
# PASS doubleclick.net  rcode=3 NXDOMAIN(已拦)
# PASS www.qq.com       rcode=0 正常解析
# 自测: 5/5 通过
```

部署好后生成描述文件：

```bash
python make_profile.py --doh https://你的域名/dns-query
# → dist/clean-dns-doh.mobileconfig，用 Safari 打开安装
```

> Cloudflare 的 `*.workers.dev` 在大陆基本不通，必须绑自己的域名。

---

## 方案 4：只拦 Safari

App Store 搜 **AdGuard**，免费版即可，在 Safari 设置里开它的内容拦截器。网页广告清净，App 内广告不管（那是付费功能）。

---

## 为什么不做「装证书深度拦截」

Jinx 收费的核心卖点是 HTTPS 中间人。它要求你：

1. 把一张**根证书**装进手机并设为完全信任
2. 让某个 App 的 VPN 接管**全部**加密流量

等价于把这个 App 的开发者变成你和每个网站之间的中间人。它能改广告，也能改登录页、看到明文密码、注入任意内容。24 元买断的软件，不值得赌这个。而且这类动私有 API 的方案，随时可能被 iOS 更新打断。

**DNS 层拦不到的部分**（抖音、淘宝、微博这类走 IP 直连 / 私有 HTTPDNS 的大厂开屏广告），承认拦不到，比装张证书假装能拦要诚实。

---

## 还能免费做的（视频后半段那些）

- 设置 → 隐私与安全性 → 跟踪 → 关闭「允许 App 请求跟踪」
- 设置 → 隐私与安全性 → Apple 广告 → 关闭个性化广告
- 微信 → 我 → 设置 → 个人信息与权限 → 个性化广告管理 → 关闭
- 各 App 内「个性化推荐」逐个关闭
- 桌面图标小红点：长按图标 → 关闭角标

---

## 文件结构

```
build.py                规则 → 配置生成器
make_profile.py         生成 DoH/DoT 描述文件
rules/ads-core.txt      广告域名清单（保守档，105 条）
doh/worker.js           Cloudflare Workers DoH
doh/app.py              阿里云函数计算 / 本地 DoH（自带 --test）
verify/run_test.py      A/B 实测脚本
verify/check_site.py    线上页面与文件校验
dist/                   生成产物
index.html              手机端安装页
check.html              装完自检页
```

## 许可

随便用。规则清单欢迎自己加。
