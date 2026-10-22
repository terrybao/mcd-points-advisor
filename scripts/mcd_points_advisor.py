#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦分精算师 (mcd-points-advisor)
麦当劳积分理财 Skill —— 监控即将过期积分，推荐最优兑换，避免积分作废。

- 实时模式 (设置环境变量 MCD_MCP_TOKEN): 通过麦当劳官方 MCP 服务读取真实数据
- 离线演示模式 (--offline): 使用内置示例数据演示完整分析逻辑，无需 Token

安全说明：仅使用只读工具 (query-my-account / mall-points-products / mall-product-detail)，
绝不调用任何写操作 (下单 / 领券 / 抽奖)，无副作用。
"""
import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from datetime import date

MCP_URL = "https://mcp.mcd.cn"


# ----------------------------- MCP Streamable HTTP 客户端 -----------------------------
class McdClient:
    def __init__(self, token):
        self.token = token
        self.session_id = None
        self._initialize()

    def _post(self, payload):
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer " + self.token,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(MCP_URL, data=data, headers=headers, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            raise RuntimeError("MCP HTTP %s: %s" % (e.code, body[:500]))
        except urllib.error.URLError as e:
            raise RuntimeError("MCP 连接失败: %s" % e.reason)
        sid = resp.headers.get("Mcp-Session-Id", self.session_id)
        if sid:
            self.session_id = sid
        ctype = resp.headers.get("Content-Type", "")
        raw = resp.read().decode("utf-8", "ignore")
        if "text/event-stream" in ctype:
            for line in raw.splitlines():
                if line.startswith("data:"):
                    chunk = line[len("data:"):].strip()
                    if chunk:
                        try:
                            return json.loads(chunk)
                        except json.JSONDecodeError:
                            continue
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _initialize(self):
        init = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcd-points-advisor", "version": "1.0.0"},
            },
        }
        self._post(init)
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def call(self, name, args=None):
        req = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
               "params": {"name": name, "arguments": args or {}}}
        out = self._post(req)
        if not out:
            raise RuntimeError("空响应: " + name)
        if "error" in out:
            raise RuntimeError("工具错误 %s: %s" % (name, out["error"]))
        content = out.get("result", {}).get("content", [])
        text = ""
        for c in content:
            if c.get("type") == "text":
                text += c.get("text", "")
        return text


# ----------------------------- 工具结果容错解析 -----------------------------
def _extract_json(text):
    """麦当劳 MCP 工具返回体为「字段说明 + ## Original Response + 真实JSON」混排，
    需定位到 JSON 部分再解析。"""
    marker = "## Original Response"
    sub = text.split(marker, 1)[1] if marker in text else text
    sub = sub.strip()
    try:
        return json.loads(sub)
    except json.JSONDecodeError:
        pass
    s, e = sub.find("{"), sub.rfind("}")
    if s != -1 and e > s:
        try:
            return json.loads(sub[s:e + 1])
        except json.JSONDecodeError:
            return None
    return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def parse_account(text):
    obj = _extract_json(text)
    if not isinstance(obj, dict):
        return None
    d = obj.get("data", obj)
    if not isinstance(d, dict):
        return None
    return {
        "availablePoints": _num(d.get("availablePoint")),
        "accumulatedPoints": _num(d.get("accumulativePoint")),
        "frozenPoints": _num(d.get("frozenPoint")),
        "expiringPoints": _num(d.get("currentMouthExpirePoint")),
        "expiredPoints": _num(d.get("expiredPoint")),
        "currency": d.get("currency", "麦享会积分"),
        "expiringLabel": "本月将过期",
    }


def parse_products(text):
    obj = _extract_json(text)
    if not isinstance(obj, dict):
        return []
    arr = obj.get("data", obj)
    if isinstance(arr, dict):
        arr = arr.get("data", [])
    if not isinstance(arr, list):
        return []
    out = []
    for it in arr:
        if not isinstance(it, dict):
            continue
        pts = _num(it.get("point", it.get("points")))
        if pts <= 0:
            continue  # 仅保留可用积分兑换的商品（过滤纯现金商品）
        out.append({
            "productId": it.get("spuId") or it.get("productId") or it.get("id"),
            "name": it.get("spuName") or it.get("name"),
            "points": pts,
            "price": it.get("price"),
        })
    return out


# ----------------------------- 积分分析核心 -----------------------------
def analyze(account, products):
    avail = float(account.get("availablePoints") or 0)
    expiring = float(account.get("expiringPoints") or 0)
    expired = float(account.get("expiredPoints") or 0)
    label = account.get("expiringLabel", "即将过期")
    cur = account.get("currency", "麦享会积分")
    lines = []
    lines.append("=== 麦分精算师 · 积分体检报告 ===")
    lines.append("积分类型   : %s" % cur)
    lines.append("可用积分   : %.1f" % avail)
    lines.append("累计积分   : %.1f" % float(account.get("accumulatedPoints") or 0))
    lines.append("冻结积分   : %.1f" % float(account.get("frozenPoints") or 0))
    if expired:
        lines.append("❗ 已过期   : %.1f（已白白损失，引以为戒）" % expired)
    if expiring:
        lines.append("⚠ %s : %.1f 积分，建议本月用掉" % (label, expiring))

    affordable = [p for p in products if float(p.get("points") or 0) <= avail]
    affordable.sort(key=lambda p: float(p.get("points") or 0), reverse=True)
    lines.append("")
    lines.append("--- 兑换建议（优先消耗过期积分，避免作废）---")
    if expiring:
        remaining = expiring
        used_avail = 0.0
        picks = []
        for p in affordable:
            cost = float(p.get("points") or 0)
            if remaining >= cost:
                picks.append((p, cost, "过期积分全额抵扣"))
                remaining -= cost
            elif remaining > 0 and cost <= avail:
                picks.append((p, cost, "过期积分抵 %.0f + 可用积分 %.0f" % (remaining, cost - remaining)))
                used_avail += cost - remaining
                remaining = 0
            elif cost <= (avail - used_avail):
                picks.append((p, cost, "可用积分兑换"))
                used_avail += cost
        if picks:
            for p, cost, how in picks:
                price = p.get("price")
                extra = ("（现金价 %s 元）" % price) if price not in (None, "0", "") else ""
                lines.append("✅ %s — %.0f 积分 %s%s" % (p.get("name", p.get("productId")), cost, how, extra))
        else:
            lines.append("当前可用积分不足以兑换任何积分商品，建议点餐攒积分或关注后续上架。")
        if remaining > 0:
            lines.append("仍有 %.0f 过期积分未消耗，可再选一件低价商品。" % remaining)
    else:
        lines.append("本月无即将过期积分，可从容规划兑换。")
    if not affordable and expiring:
        lines.append("（提示：当前商城返回的多为现金购买商品，已自动过滤不可用积分兑换的。）")
    return "\n".join(lines)


# ----------------------------- 离线演示数据 -----------------------------
OFFLINE_ACCOUNT = {
    "availablePoints": 500.0,
    "accumulatedPoints": 12800.0,
    "frozenPoints": 0.0,
    "expiringPoints": 200.0,
    "expiredPoints": 563.6,
    "currency": "麦享会积分",
    "expiringLabel": "本月将过期",
}
OFFLINE_PRODUCTS = [
    {"productId": "P001", "name": "麦辣鸡腿堡兑换券", "points": 100.0, "price": "0"},
    {"productId": "P002", "name": "巨无霸兑换券", "points": 150.0, "price": "0"},
    {"productId": "P003", "name": "薯条买一赠一券", "points": 50.0, "price": "0"},
    {"productId": "P004", "name": "10元现金抵扣券", "points": 80.0, "price": "0"},
    {"productId": "P005", "name": "麦咖啡中杯券", "points": 60.0, "price": "0"},
]


def main():
    ap = argparse.ArgumentParser(description="麦当劳积分理财 Skill")
    ap.add_argument("--offline", action="store_true", help="离线演示模式（无需 Token）")
    ap.add_argument("--detail", action="store_true", help="实时模式额外拉取每个商品详情")
    args = ap.parse_args()

    if args.offline or not os.environ.get("MCD_MCP_TOKEN"):
        if not args.offline:
            print("[提示] 未检测到 MCD_MCP_TOKEN，自动切换离线演示模式。\n")
        account = OFFLINE_ACCOUNT
        products = OFFLINE_PRODUCTS
    else:
        token = os.environ["MCD_MCP_TOKEN"]
        client = McdClient(token)
        print("[实时] 正在读取积分账户...")
        account = parse_account(client.call("query-my-account")) or {}
        if not account.get("availablePoints"):
            print("[警告] 无法解析账户数据，原始返回如下，请核对字段：")
            print(client.call("query-my-account"))
            return
        print("[实时] 正在拉取麦麦商城商品...")
        products = parse_products(client.call("mall-points-products"))
        if args.detail:
            for p in products[:10]:
                if p.get("productId"):
                    det = client.call("mall-product-detail", {"productId": p["productId"]})
                    print("[详情] %s: %s" % (p.get("name"), det[:200]))

    print()
    print(analyze(account, products))


if __name__ == "__main__":
    main()
