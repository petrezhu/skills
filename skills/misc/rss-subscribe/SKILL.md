---
name: rss-subscribe
description: Use when 老己 wants to subscribe to a website's updates / 新增 RSS 订阅 / 把某网站加进订阅源 / 这个网站有没有 RSS. Detects native RSS first, falls back to self-hosted RSSHub routes for sites without feeds, registers the subscription into the manifest and verifies it actually parses. Trigger on 订阅, RSS 源, RSSHub, 加个订阅, 这个网站有没有 RSS, 新增订阅源, RSS for, subscribe to this website, add this site to my feeds.
---

# rss-subscribe：新增网站 RSS 订阅

把一个网站（**有 RSS 源的和没有的都算**）接进订阅清单。四步走完，最后必须能粘出一条可直接订阅的 URL。

> 本 skill 由 `feed-sourcing` 合并而来（2026-09-27，老己拍板留此废彼），原文件在
> `/root/.hermes/profiles/main/skills/.archive/feed-sourcing-archived-20260927-112158/`（不在 git 仓库内）。
> 分工：本 skill 负责 sourcing（拿到可用 URL）；轮询/去重/推送归 `blogwatcher`。

## 铁律

1. **先原生，后 RSSHub**。站点自带 RSS 更快、更稳、不依赖 mac-lab 开机。
2. **必须实测拉到条目才算成功**。`add` 验证不通过就直接拒收，**没有绕过开关**。
3. **反爬站 ≠ 无 RSS 站**。`detect_feed.py` 返回 `blocked` 时不能下"该站没有源"的结论。
4. **输出可直接粘进 RSS 阅读器的完整地址**，别只丢一个路由路径。

## Step 1：探测原生源

```bash
python3 <skill_root>/scripts/detect_feed.py <站点URL或域名>
```

| status | 含义 | 下一步 |
|---|---|---|
| `ok` | 找到原生 feed | 用 `recommended`，跳 Step 3 |
| `none` | 站点可达但确实无源 | Step 2 查 RSSHub |
| `blocked` | 反爬/限流（403/429…） | Step 2，原生探测作废 |
| `error` | 站点不可达 | 查网络/URL，别硬编 feed |

**别手写 curl 循环探测**，脚本已修掉两个真实 bug：漏掉 `/blog/` 这类路径前缀、被 Cloudflare 按 UA 返回 403 骗成"无源"。

## Step 2：无源站查 RSSHub 路由

自建实例 `https://rss.petrezhu.cn`（Basic Auth，见文末「凭据」）。先确认实例活着：

```bash
CRED=$(grep -E '^(账号|密码): ' /root/.hermes/profiles/main/secrets/rsshub-basic-auth \
       | awk -F': ' '{print $2}' | paste -sd: -)
curl -s -u "$CRED" -o /dev/null -w '%{http_code}\n' https://rss.petrezhu.cn/healthz   # 期望 200
```

**可用端点只有两个**（2026-09-27 实测）：

```
GET /api/radar/rules   200   按域名组织的 URL→路由 规则表（1476 个域名）
GET /api/reference     200   API 文档
GET /api/routes        404   不存在！别再写这个端点
```

按域名查某站支持哪些路由：

```bash
curl -s -u "$CRED" https://rss.petrezhu.cn/api/radar/rules \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
for dom, v in d.items():
    if 'bilibili' in dom:
        for k, rules in v.items():
            if k.startswith('_') or not isinstance(rules, list): continue
            for r in rules[:6]: print(k, r.get('source'), '->', r.get('target'))
        break"
```

路由格式 `/<平台>/<内容类型>/<参数>`。**平台已有成熟路由的不要写爬虫**：
Bilibili、微博、知乎、微信公众号、抖音、小红书、Telegram、YouTube、GitHub、Reddit、Steam、V2EX。

通用参数（任意路由可用）：`?limit=10`、`?filter=关键词`、`?filterout=`、`?mode=fulltext`

查不到 → 路由文档 <https://docs.rsshub.app/routes/<平台>>。仍无 → 报告"该站无现成路由"并给选项：
写路由（外部 skill：<https://github.com/AboutRSS/rsshub-route-authoring-skill>，**未安装在本机**，要用需先装）或
Agent-Reach 单次读取。**不要硬编未验证的路由。**

## Step 2.5：判读返回状态码（关键）

RSSHub 的失败**只看状态码，不看 body**，错误页也是 HTML，肉眼极易误判成"欢迎页/正常页"：

```
200  路由可用，返回真 XML/Atom     → 可入册
404  路由不存在（NotFoundError）    → 路由名错了，回 Step 2 查规则表
503  路由存在但执行失败            → 依赖缺失或上游风控，不是路由问题
301  重定向                        → 路径写法需调整
```

**503 ≠ 路由不存在。** 本实例 503 有三个成因，都要排除：

1. **冷启动首请求**：RSSHub 刚重启、缓存未热时，首请求会 503 或跑满 20~30s。
   重试一次即可（实测：zhihu 首次 27.8s，随后 4 次全部 0.25s）。别据此判定路由坏了。
2. **缺 Chromium**：该路由需要渲染而 Playwright Chromium 未装
   （`browserType.launch: Executable doesn't exist`）。装法：

```bash
cd ~/RSSHub && npx patchright install chromium    # 182MB，装完重启 RSSHub 进程
```

3. **上游风控**（间歇，装好依赖也会中）：站点接口把请求拦了。实测 B站
   `bilibili/user/video`：`API 风控校验失败 -352 → 回退 browser mode → 412 → 503`。
   同一 URL 连打三次可能是 `503 / 503 / 200`，**重试即通**；命中 RSSHub 内存缓存则稳定 200（15ms）。
   所以判读 503 要连打 2~3 次，别一发定生死。

区分方法：看 Mac 上的 `~/rsshub.log`，503 必带具体 error 行（三种成因各带不同错误）。

真实路由名常与文档不同，实测过：
`/github/issue/vuejs/core` ✓（**单数 issue**）、`/github/release/…` ✗404、`/github/commits/…` ✗404

## Step 3：入册

```bash
# 原生源
python3 <skill_root>/scripts/subscribe.py add \
  --name "站点名" --feed "<原生feed URL>" --type native --site "<站点URL>"

# RSSHub 源
python3 <skill_root>/scripts/subscribe.py add \
  --name "站点名" --feed "https://rss.petrezhu.cn/<route>" --type rsshub
```

`--name` 用中文短名，清单里要好扫。返回 `rejected` 就如实报告原因。

可选参数 `--group`（显式分组，覆盖自动归类）、`--filterout`（排除式正则，如
`【公告全知道】|【早报】`），导出 OPML 时生效。例：

```bash
python3 <skill_root>/scripts/subscribe.py add \
  --name "财联社-电报" --feed "https://rss.petrezhu.cn/cls/telegraph" --type rsshub \
  --group "财经新闻" --filterout "【公告全知道】|【风口研报】|【早报】|研报"
```

**没有现成路由时的兜底**（按优先级）：
1. 普通文章站 → CSS 选择器抓取可行，但会随改版静默腐烂，只适合单次取用
2. 登录墙/重反爬站 → **不适合长期订阅**，建议单次显式抓取，别伪装成订阅
3. 高频平台 → 写 RSSHub 路由

## Step 4：验证并汇报

```bash
python3 <skill_root>/scripts/subscribe.py list      # 总览
python3 <skill_root>/scripts/subscribe.py verify    # 逐个重新拉取
```

## Step 5：导出 OPML（给各 RSS 阅读器）

订阅清单是**唯一真相源**，随时导出一份 OPML 供 Feedly / NetNewsWire / Inoreader 等阅读器导入：

```bash
python3 <skill_root>/scripts/subscribe.py export-opml --out ~/follows.opml
```

- 自动按类型分组：`B站UP主 / 播客 / 财经新闻 / 政务政策 / 科技媒体 / 博客·媒体`；
  源上用 `--group` 显式指定则有更高优先级，不受自动归类约束
- 源上的 `filterout` 字段（排除式正则，纯文本）**只在导出时**拼进 `xmlUrl`
  （`?filterout=<URL编码的正则>`）→ 阅读器拿到的就是过滤后的 feed，yaml 保持可读
- 过滤规则不在脚本里硬编码：`--filterout '关键词1|关键词2'` 入册时写进清单，改规则改清单字段即可

汇报格式（三行内说完）：

```
✓ <站点名> · <feed标题> · N 条
  订阅地址: <完整 URL>
  清单: <当前总数> 项
```

## 文件与实例

- 清单：`<workspace>/data/subscriptions.yaml`（唯一真相源，Git 可备份）
- 脚本：`scripts/detect_feed.py`（探测）、`scripts/subscribe.py`（登记/验证/导出 OPML）、
  `scripts/rsshub_auth.py`（凭据，自动被前者调用）
- 实例：mac-lab `~/RSSHub`，pnpm 原生部署（**未用 Docker**），入口 `dist/index.mjs`，端口 1200，环境
  `NODE_ENV=production CACHE_TYPE=memory CACHE_EXPIRE=300 PORT=1200`
- **开机自启**：launchd `com.petrezhu.rsshub`（`~/Library/LaunchAgents/`，`RunAtLoad` + `KeepAlive`，
  挂了自动拉起，实测 kill 后秒回）。改配置用 `launchctl kickstart -k gui/$(id -u)/com.petrezhu.rsshub`
- 浏览器渲染路由（B站等）需要 Chromium：`cd ~/RSSHub && npx patchright install chromium`
- 实例健康：`GET /healthz`；日志 `~/rsshub.log`（Mac 上）

**当前状态（2026-09-27 已全通）**：`rss.petrezhu.cn` → `113.45.170.85`，三网 DNS 生效（TTL 300），
HTTPS 已上线，RSSHub 源可正常入册。

- vhost：`/www/server/panel/vhost/nginx/rss.petrezhu.cn.conf`（80 → 301 跳 https，443 反代回源
  `http://10.8.0.10:1200`，Basic Auth）
- 证书：Let's Encrypt ECC，装在 `/www/server/panel/vhost/cert/rss.petrezhu.cn/`，续期自动
  `kill -HUP 1606`（reloadcmd 已配好）
- ⚠️ nginx **不要用 `systemctl restart`**（BT Panel 自管）；改配置用 `kill -HUP 1606`。
  注意 `/www/server/nginx/logs/nginx.pid` 是**陈旧的**（指向早已不存在的 647150），
  一律用 `ps -eo pid,ppid,cmd | grep 'nginx: master'` 取真实 PID（当前是 1606）。

## 凭据

RSSHub 实例有 Basic Auth。账号密码**不要写进对话，不要写进清单，不要进 git**。

`scripts/rsshub_auth.py` 已经自动处理：探测、验证在请求 `rss.petrezhu.cn` 时会自动带上
认证头，**入册 RSSHub 源时你不需要手动传任何凭据**。凭据文件：

```
/root/.hermes/profiles/main/secrets/rsshub-basic-auth   # 权限 600
```

⚠️ **不要放回 `cache/scratch/`**，那个目录 24 小时空闲即清理，届时所有 RSSHub 源会静默 401。

只有命令行直接 curl 实例时才需要手动取凭据：

```bash
CRED=$(grep -E '^(账号|密码): ' /root/.hermes/profiles/main/secrets/rsshub-basic-auth \
       | awk -F': ' '{print $2}' | paste -sd: -)
```

给你的 RSS 阅读器用时，在阅读器里填 Basic Auth 账号密码（**不要把密码拼进 feed URL 再存进清单**）。

## 坑（都踩过）

- **`probe_link_tags` 必须以「抓到 HTML 的那个 URL」为基准**解析相对 href，不能用域名根，否则 `/blog/atom.xml` 这种带前缀的源必丢。
- **link-tag 命中不等于能用**。阮一峰首页 alternate 指向境外 FeedBurner，本机连不通；曾因此把整站误判成无源。现在是先验 link-tag，验不出再补盲探。
- **路径盲探要同时试「输入路径所在目录」和「域名根」**。
- **curl 会 403 而 Python 200**（Cloudflare 按 UA 分流）。判断可达性一律以脚本输出为准，别用 curl 抽查下结论。
- **反爬状态码（403/406/429/503）返回 `blocked`，不是 `none`**，含义完全不同。
- **RSSHub 错误页是 HTML**，只有状态码可信（Step 2.5）。
- **路由会腐烂**：上游改版让路由静默失效。监控连续失败时按坏路由处理，别当网络抖动重试。
- **无 RSS 源网站的可用性取决于 mac-lab 是否开机**，原生源没有这个约束，这是"先原生后 RSSHub"的硬理由。
