import argparse
import json
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests
from lxml import etree
from playwright.sync_api import sync_playwright


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
EXAMPLE_CONFIG_FILE = BASE_DIR / "config.json.example"
DEFAULT_CONFIG = {
    "portal_url": "https://yjsjw-443.webvpn.scut.edu.cn/",
    "target_url": None,
    "homepage_referer": None,
    "success_text": "研究生教学教务管理系统",
    "watch_xpath": '//*[@id="SC_DGRD_PP_APY_SC_ZP_DESCR$0"]',
    "request_timeout_seconds": 30,
    "monitor_interval_seconds": 300,
    "cookie_file": "cookies.json",
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36"
    ),
    "notify": {
        "notify_url": "http://14.103.144.178:7790/send/friend",
        "notify_target": "1061700625",
        "notify_key": "",
        "serverchan_sendkey": "",
    },
}
SERVERCHAN_API_TEMPLATE = "https://sctapi.ftqq.com/{sendkey}.send"


@dataclass
class RuntimeConfig:
    portal_url: str
    target_url: str
    homepage_referer: str
    success_text: str
    watch_xpath: str
    request_timeout_seconds: int
    monitor_interval_seconds: int
    cookie_file: Path
    user_agent: str
    notify_url: str
    notify_target: str
    notify_key: str
    serverchan_sendkey: str


@dataclass
class MonitorState:
    last_text: Optional[str] = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    session_invalid_notified: bool = False


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = _deep_merge(base[key], value)
        else:
            merged[key] = value
    return merged


def _build_default_target_url(portal_url: str) -> str:
    return (
        f"{portal_url}psc/ps_9/EMPLOYEE/SA/c/"
        "SC_CUSTOM_MENU.SC_BS_PP_REC_COM.GBL"
        "?FolderPath=PORTAL_ROOT_OBJECT.SC_XWGL_MGT.SC_BSXWGL_MGT."
        "SC_BSLWSSGL_MGT.SC_BS_PP_REC_COM_GBL"
        "&IsFolder=false"
        "&IgnoreParamTempl=FolderPath%2cIsFolder"
    )


def _build_default_homepage_referer(portal_url: str) -> str:
    return (
        f"{portal_url}psp/ps/EMPLOYEE/SA/s/"
        "WEBLIB_PTPP_SC.HOMEPAGE.FieldFormula.IScript_AppHP"
        "?pt_fname=CO_EMPLOYEE_SELF_SERVICE"
        "&FolderPath=PORTAL_ROOT_OBJECT.CO_EMPLOYEE_SELF_SERVICE"
        "&IsFolder=true"
    )


def load_runtime_config() -> RuntimeConfig:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"未找到配置文件: {CONFIG_FILE}。"
            f"请先将 {EXAMPLE_CONFIG_FILE.name} 复制为 {CONFIG_FILE.name} 并填写配置。"
        )

    raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    merged = _deep_merge(DEFAULT_CONFIG, raw)

    portal_url = str(merged["portal_url"])
    target_url = merged.get("target_url") or _build_default_target_url(portal_url)
    homepage_referer = merged.get("homepage_referer") or _build_default_homepage_referer(portal_url)
    cookie_file = Path(merged.get("cookie_file") or "cookies.json")
    if not cookie_file.is_absolute():
        cookie_file = BASE_DIR / cookie_file

    notify = merged.get("notify") or {}
    return RuntimeConfig(
        portal_url=portal_url,
        target_url=str(target_url),
        homepage_referer=str(homepage_referer),
        success_text=str(merged["success_text"]),
        watch_xpath=str(merged["watch_xpath"]),
        request_timeout_seconds=int(merged["request_timeout_seconds"]),
        monitor_interval_seconds=int(merged["monitor_interval_seconds"]),
        cookie_file=cookie_file,
        user_agent=str(merged["user_agent"]),
        notify_url=str(notify.get("notify_url") or ""),
        notify_target=str(notify.get("notify_target") or ""),
        notify_key=str(notify.get("notify_key") or ""),
        serverchan_sendkey=str(notify.get("serverchan_sendkey") or ""),
    )


CONFIG = load_runtime_config()
HEADERS = {
    "User-Agent": CONFIG.user_agent,
    "Referer": CONFIG.homepage_referer,
}


def send_message_via_notify_url(msg: str) -> None:
    if not (CONFIG.notify_url and CONFIG.notify_target and CONFIG.notify_key):
        return
    resp = requests.get(
        CONFIG.notify_url,
        params={"target": CONFIG.notify_target, "msg": msg, "key": CONFIG.notify_key},
        timeout=10,
    )
    resp.raise_for_status()



def send_message_via_serverchan(title: str, desp: str) -> None:
    sendkey = CONFIG.serverchan_sendkey.strip()
    if not sendkey:
        return

    api_url = SERVERCHAN_API_TEMPLATE.format(sendkey=sendkey)
    resp = requests.post(api_url, data={"title": title, "desp": desp}, timeout=10)
    resp.raise_for_status()

    try:
        data = resp.json()
    except ValueError:
        data = None

    if isinstance(data, dict) and data.get("code") not in (0, None):
        raise RuntimeError(f"Server酱返回异常: {data}")



def send_message(msg: str, title: str = "论文盲审监控通知") -> None:
    errors = []

    try:
        send_message_via_notify_url(msg)
        if CONFIG.notify_url:
            print("NOTIFY_URL 通知发送成功")
    except Exception as exc:
        errors.append(f"NOTIFY_URL: {exc}")

    try:
        send_message_via_serverchan(title=title, desp=msg)
        if CONFIG.serverchan_sendkey.strip():
            print("Server酱通知发送成功")
    except Exception as exc:
        errors.append(f"Server酱: {exc}")

    if errors:
        print("部分通知通道失败 -> " + " | ".join(errors))



def send_notification(old_text: str, new_text: str) -> None:
    print("=" * 80)
    print("检测到内容更新")
    print(f"更新前: {old_text!r}")
    print(f"更新后: {new_text!r}")
    print("=" * 80)

    title = "论文盲审状态已更新"
    msg = f"论文盲审状态已更新\n更新前: {old_text}\n更新后: {new_text}"
    send_message(msg, title=title)



def send_session_invalid_notification(
    msg: str = "论文盲审页面对应的教务门户登录态已失效，请尽快重新登录处理。",
) -> None:
    send_message(msg, title="论文盲审页面登录态失效")



def ensure_browser_installed() -> None:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception as exc:
        error_text = str(exc)
        if "Executable doesn't exist" in error_text:
            print("未检测到 Chromium，开始自动安装...")
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True,
            )
            print("Chromium 安装完成。")
        else:
            raise



def build_browser(headless: bool = False):
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=headless,
        args=["--window-size=960,720"],
    )
    context = browser.new_context(viewport={"width": 960, "height": 720})
    page = context.new_page()
    return playwright, browser, context, page



def wait_for_manual_login(page) -> None:
    page.goto(CONFIG.portal_url, wait_until="domcontentloaded")
    print("请在浏览器中手动登录，出现'研究生教学教务管理系统'后会继续。")  
    page.wait_for_selector(f"text={CONFIG.success_text}", timeout=0)
    print("检测到登录成功。")



def sync_cookies(context, session: requests.Session) -> None:
    cookies = context.cookies()
    for cookie in cookies:
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
        )



def save_cookies(context, cookie_file: Path = CONFIG.cookie_file) -> None:
    cookies = context.cookies()
    cookie_file.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保存 cookies 到 {cookie_file}")



def load_cookies(session: requests.Session, cookie_file: Path = CONFIG.cookie_file) -> None:
    cookies = json.loads(cookie_file.read_text(encoding="utf-8"))
    for cookie in cookies:
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
        )



def fetch_page(session: requests.Session) -> tuple[Optional[str], requests.Response]:
    resp = session.get(CONFIG.target_url, headers=HEADERS, timeout=CONFIG.request_timeout_seconds)
    resp.raise_for_status()

    html = etree.HTML(resp.text)
    if html is None:
        return None, resp

    result = html.xpath(CONFIG.watch_xpath)
    if not result:
        return None, resp

    text = "".join(result[0].itertext()).strip()
    return text, resp



def is_session_invalid(resp: requests.Response, watched_text: Optional[str]) -> bool:
    body = resp.text or ""
    url = resp.url or ""

    if "You are not authorized to access this component" in body:
        return True
    if "PSLOGIN" in url.upper():
        return True
    if "signin" in url.lower() or "login" in url.lower():
        return True
    if watched_text is None and ("登录" in body or "login" in body.lower()):
        return True
    return False



def interruptible_wait(
    stop_event: threading.Event,
    total_seconds: int,
    step: float = 1.0,
) -> bool:
    end_time = time.time() + total_seconds
    while time.time() < end_time:
        remaining = end_time - time.time()
        timeout = min(step, max(0.0, remaining))
        if stop_event.wait(timeout):
            return True
    return False



def handle_session_invalid(state: MonitorState, session: requests.Session) -> bool:
    if not state.session_invalid_notified:
        send_session_invalid_notification("论文盲审页面对应的教务门户登录态已失效，请你重新处理登录。")
        state.session_invalid_notified = True

    print("准备临时拉起浏览器，等待你手动重新登录。")

    playwright = None
    browser = None
    try:
        ensure_browser_installed()
        playwright, browser, context, page = build_browser(headless=False)
        wait_for_manual_login(page)
        sync_cookies(context, session)
        save_cookies(context)
        state.session_invalid_notified = False
        print("已重新获取登录态，浏览器已关闭，继续监控。")
        return True
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f"重新登录失败: {exc}")
        traceback.print_exc()
        return False
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass



def monitor_loop(session: requests.Session, state: MonitorState, interval_seconds: int) -> None:
    while not state.stop_event.is_set():
        try:
            watched_text, resp = fetch_page(session)
            if is_session_invalid(resp, watched_text):
                ok = handle_session_invalid(state, session)
                if not ok:
                    break
                continue

            state.session_invalid_notified = False

            if watched_text is None:
                raise RuntimeError("XPath 未匹配到目标内容，页面结构可能变化。")

            now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            print(f"[{now_str}] 当前内容: {watched_text!r}")

            if state.last_text is None:
                state.last_text = watched_text
                print("已记录初始内容。")
            elif watched_text != state.last_text:
                old_text = state.last_text
                state.last_text = watched_text
                send_notification(old_text, watched_text)
            else:
                print("内容未变化。")
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[监控] 异常: {exc}")
            traceback.print_exc()

        interrupted = interruptible_wait(state.stop_event, interval_seconds)
        if interrupted:
            break



def validate_or_load_cookie(state: MonitorState) -> tuple[bool, Optional[requests.Session]]:
    if not CONFIG.cookie_file.exists():
        return False, None

    session = requests.Session()
    try:
        load_cookies(session)
        watched_text, resp = fetch_page(session)
        if is_session_invalid(resp, watched_text):
            print("检测到本地 cookie 已失效。")
            return False, None

        if watched_text is not None:
            state.last_text = watched_text
            print(f"当前内容: {watched_text!r}")
        return True, session
    except Exception as exc:
        print(f"cookie 校验失败: {exc}")
        return False, None



def login_and_save_cookie() -> None:
    ensure_browser_installed()
    playwright = None
    browser = None
    try:
        playwright, browser, context, page = build_browser(headless=False)
        wait_for_manual_login(page)
        save_cookies(context)
        print("登录态已保存。")
    finally:
        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()



def check_once() -> int:
    state = MonitorState()
    ok, session = validate_or_load_cookie(state)
    if not ok or session is None:
        print("未发现有效 cookie，请先运行 login 子命令。")
        return 2

    watched_text, resp = fetch_page(session)
    if is_session_invalid(resp, watched_text):
        print("登录态已失效，请先重新登录。")
        return 3

    if watched_text is None:
        print("XPath 未匹配到目标内容，页面结构可能变化。")
        return 4

    print(watched_text)
    return 0



def run_monitor(interval_seconds: int) -> int:
    state = MonitorState()
    ok, session = validate_or_load_cookie(state)
    if not ok or session is None:
        print("未发现有效 cookie，先进入手动登录流程。")
        login_and_save_cookie()
        ok, session = validate_or_load_cookie(state)
        if not ok or session is None:
            print("登录后仍无法建立有效会话。")
            return 2

    try:
        monitor_loop(session, state, interval_seconds)
        return 0
    except KeyboardInterrupt:
        print("\n收到 Ctrl+C，监控退出。")
        return 130
    finally:
        state.stop_event.set()



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SCUT graduate portal monitor helper for OpenClaw")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("login", help="Open a browser for manual login and save cookies")
    subparsers.add_parser("check-once", help="Check the watched portal text once using saved cookies")

    monitor_parser = subparsers.add_parser("monitor", help="Continuously monitor the watched portal text")
    monitor_parser.add_argument(
        "--interval-seconds",
        type=int,
        default=CONFIG.monitor_interval_seconds,
        help=f"Polling interval in seconds, default {CONFIG.monitor_interval_seconds}",
    )
    return parser



def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "login":
        login_and_save_cookie()
        return 0
    if args.command == "check-once":
        return check_once()
    if args.command == "monitor":
        return run_monitor(interval_seconds=args.interval_seconds)

    parser.error("未知命令")
    return 1


if __name__ == "__main__":
    sys.exit(main())
