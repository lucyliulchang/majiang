"""生产 UI 冒烟：桌面 /majiangapp 与手机 /mjmobile 的登录页版本号 + 真实结算面板。

流程：
1. 桌面/手机登录页读版本号（应显示 v1.1.0）；
2. 两个浏览器（桌面 1440x900、手机横屏 844x390）同时以观战身份进真实牌桌；
3. 通过 ssh 触发机器人开局（go_game 文件），等结算浮层出现；
4. 各自截图 + 抓正文文本（结算面板的番种清单）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

EVID = Path(r"d:/StevenLianData/0301. Private Project/gitData/majiang/plan/I7-evidence")
EVID.mkdir(parents=True, exist_ok=True)

TOKEN = sys.argv[1]
ROOM_CODE = sys.argv[2]
DESKTOP = "https://www.iottest.online/majiangapp"
MOBILE = "https://www.iottest.online/mjmobile"
SSH = [
    "ssh",
    "-i",
    r"D:\data\keys\codeops_ed25519",
    "-o",
    "StrictHostKeyChecking=no",
    "-o",
    "ConnectTimeout=15",
    "codeops@www.iottest.online",
]
FAN_KEYS = ("断幺", "清一色", "七小对", "一般高", "将牌", "门清", "独赢", "258赢", "连6", "缺门", "箭刻")
report: dict = {"room_code": ROOM_CODE, "steps": []}


def note(name: str, ok: bool, detail=None) -> None:
    report["steps"].append({"step": name, "pass": bool(ok), "detail": detail})
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {name}" + (f" -> {detail}" if detail else ""))


def wait_settlement(page, timeout_s: int = 180):
    """轮询页面文本，等结算面板出现（出现任一番种关键字即认为面板已渲染）。"""
    deadline = timeout_s
    body = ""
    while deadline > 0:
        body = page.inner_text("body")
        if ("登录牌桌" not in body) and any(key in body for key in FAN_KEYS):
            return body
        page.wait_for_timeout(2000)
        deadline -= 2
    return body


with sync_playwright() as play:
    try:
        browser = play.chromium.launch()
    except Exception as error:
        print("chromium 不可用，改用系统浏览器：", str(error)[:60])
        try:
            browser = play.chromium.launch(channel="chrome")
        except Exception:
            browser = play.chromium.launch(channel="msedge")

    # ---------- 登录页版本号 ----------
    guest = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = guest.new_page()
    page.goto(f"{DESKTOP}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    version_text = page.locator("text=/v\\d+\\.\\d+\\.\\d+/").first.inner_text()
    page.screenshot(path=str(EVID / "desktop-01-login.png"))
    note("桌面登录页版本号", "1.1.0" in version_text, version_text)
    guest.close()

    mguest = browser.new_context(viewport={"width": 844, "height": 390}, locale="zh-CN", is_mobile=True, has_touch=True)
    mlogin = mguest.new_page()
    mlogin.goto(f"{MOBILE}/login", wait_until="domcontentloaded")
    mlogin.wait_for_timeout(2500)
    mversion = mlogin.locator("text=/v\\d+\\.\\d+\\.\\d+/").first.inner_text()
    mlogin.screenshot(path=str(EVID / "mobile-01-login.png"))
    note("手机登录页版本号", "1.1.0" in mversion, mversion)
    mguest.close()

    # ---------- 桌面 + 手机同时观战进桌 ----------
    desktop = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    desktop.add_init_script(f"window.localStorage.setItem('mj_token', {json.dumps(TOKEN)})")
    dpage = desktop.new_page()
    dpage.goto(f"{DESKTOP}/room/{ROOM_CODE}", wait_until="domcontentloaded")

    mobile = browser.new_context(viewport={"width": 844, "height": 390}, locale="zh-CN", is_mobile=True, has_touch=True)
    mobile.add_init_script(f"window.localStorage.setItem('mj_token', {json.dumps(TOKEN)})")
    mpage = mobile.new_page()
    mpage.goto(f"{MOBILE}/room/{ROOM_CODE}", wait_until="domcontentloaded")
    dpage.wait_for_timeout(3000)
    mpage.wait_for_timeout(1000)

    # ---------- 触发机器人开局 ----------
    subprocess.run(SSH + ["rm -f /home/codeops/mj_deploy2/go_game"], check=False)
    subprocess.run(SSH + ["touch /home/codeops/mj_deploy2/go_game"], check=False)
    print("已触发开局")

    dbody = wait_settlement(dpage)
    dpage.screenshot(path=str(EVID / "desktop-02-room-result.png"), full_page=True)
    (EVID / "desktop-02-room-result.txt").write_text(dbody, encoding="utf-8")
    d_fans = [key for key in FAN_KEYS if key in dbody]
    note("桌面牌桌/结算面板渲染", bool(d_fans) and "登录牌桌" not in dbody, {"番种": d_fans})

    mbody = wait_settlement(mpage)
    mpage.screenshot(path=str(EVID / "mobile-02-room-result.png"), full_page=True)
    (EVID / "mobile-02-room-result.txt").write_text(mbody, encoding="utf-8")
    m_fans = [key for key in FAN_KEYS if key in mbody]
    overflow = mpage.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    note("手机牌桌/结算面板渲染", bool(m_fans) and overflow <= 1, {"番种": m_fans, "h_overflow": overflow})

    # ---------- 大厅（先收房，再检查列表为空） ----------
    subprocess.run(SSH + ["touch /home/codeops/mj_deploy2/release_room"], check=False)
    dpage.wait_for_timeout(8000)
    dpage.goto(f"{DESKTOP}/", wait_until="domcontentloaded")
    dpage.wait_for_timeout(3000)
    lobby_text = dpage.inner_text("body")
    dpage.screenshot(path=str(EVID / "desktop-03-lobby.png"), full_page=True)
    (EVID / "desktop-03-lobby.txt").write_text(lobby_text, encoding="utf-8")
    note("桌面大厅不含已结束房间", ROOM_CODE not in lobby_text, {"含房号": ROOM_CODE in lobby_text})

    mpage.goto(f"{MOBILE}/", wait_until="domcontentloaded")
    mpage.wait_for_timeout(3000)
    mlobby = mpage.inner_text("body")
    mpage.screenshot(path=str(EVID / "mobile-03-lobby.png"), full_page=True)
    (EVID / "mobile-03-lobby.txt").write_text(mlobby, encoding="utf-8")
    note("手机大厅不含已结束房间", ROOM_CODE not in mlobby, {"含房号": ROOM_CODE in mlobby})

    desktop.close()
    mobile.close()
    browser.close()

report["all_pass"] = all(item["pass"] for item in report["steps"])
(EVID / "ui-smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"all_pass": report["all_pass"]}, ensure_ascii=False))
