// 免费去广告 · 自建 DoH 过滤解析器（Cloudflare Workers 版，免费额度 10 万次/天）
//
// 作用：给 iOS 一个「会过滤广告」的加密 DNS 地址，配合描述文件使用：
//   python make_profile.py --doh https://你的域名/dns-query
//
// 部署：
//   1. npm i -g wrangler && wrangler login
//   2. wrangler deploy worker.js --name adblock-doh --compatibility-date 2024-11-01
//   3. 绑定自定义域名（workers.dev 在大陆经常不通，务必用自己的域名）
//
// 上游用的是腾讯 doh.pub（国内快、不记录）；命中广告域名直接回 NXDOMAIN。

const UPSTREAM = "https://doh.pub/dns-query";

// 需要拦截的域名后缀（子域名一并拦）。想加就往下加。
const BLOCK = [
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
];

const b64uDecode = s => {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
};

// 返回 { name, qEnd }，qEnd 是 question 段结束的字节偏移
function parseQuestion(msg) {
  let off = 12;
  const labels = [];
  while (off < msg.length) {
    const len = msg[off];
    if (len === 0) { off++; break; }
    if (len & 0xc0) { off += 2; break; } // 压缩指针，正常查询不会出现
    labels.push(String.fromCharCode(...msg.subarray(off + 1, off + 1 + len)));
    off += 1 + len;
  }
  off += 4; // qtype + qclass
  return { name: labels.join(".").toLowerCase(), qEnd: off };
}

function isBlocked(name) {
  return BLOCK.some(d => name === d || name.endsWith("." + d));
}

// 构造 NXDOMAIN 响应：只保留 header + question
function nxdomain(msg, qEnd) {
  const out = msg.slice(0, qEnd);
  const dv = new DataView(out.buffer, out.byteOffset, out.byteLength);
  dv.setUint16(2, 0x8183); // QR=1 RD=1 RA=1 RCODE=3
  dv.setUint16(6, 0);
  dv.setUint16(8, 0);
  dv.setUint16(10, 0);
  return out;
}

export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (request.method === "GET" && !url.searchParams.get("dns")) {
      return new Response("adblock DoH ready", { headers: { "content-type": "text/plain" } });
    }

    let query;
    try {
      query = request.method === "POST"
        ? new Uint8Array(await request.arrayBuffer())
        : b64uDecode(url.searchParams.get("dns"));
    } catch {
      return new Response("bad request", { status: 400 });
    }
    if (query.length < 17) return new Response("bad query", { status: 400 });

    const { name, qEnd } = parseQuestion(query);
    if (isBlocked(name)) {
      return new Response(nxdomain(query, qEnd), {
        headers: { "content-type": "application/dns-message", "cache-control": "max-age=60" },
      });
    }

    const up = await fetch(UPSTREAM, {
      method: "POST",
      headers: { "content-type": "application/dns-message" },
      body: query,
    });
    return new Response(up.body, {
      status: up.status,
      headers: {
        "content-type": "application/dns-message",
        "cache-control": "max-age=60",
      },
    });
  },
};
