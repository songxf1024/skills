import argparse
import builtins
import base64
import os
import hashlib
import json
import re
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
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
EXAMPLE_CONFIG_FILE = BASE_DIR / "config.json.example"
DEFAULT_CONFIG = {
    "portal_url": "https://yjsjw.scut.edu.cn/", # "https://yjsjw-443.webvpn.scut.edu.cn/"
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
    "image_upload": {
        "enabled": True,
        "api_url": "https://img.scdn.io/api/v1.php",
        "output_format": "png",
        "cdn_domain": "default",
        "password_enabled": False,
        "image_password": "",
        "request_timeout_seconds": 30,
        "url_file": "login_qrcode_url.txt",
        "response_file": "login_qrcode_upload.json",
    },
}
SERVERCHAN_API_TEMPLATE = "https://sctapi.ftqq.com/{sendkey}.send"
LOGIN_QRCODE_SELECTOR = "#qrcodeQQLogin"
LOGIN_QRCODE_IMAGE_SELECTOR = f"{LOGIN_QRCODE_SELECTOR} img"
LOGIN_QRCODE_IMAGE_FILE = BASE_DIR / "login_qrcode.png"
LOGIN_QRCODE_DATA_FILE = BASE_DIR / "login_qrcode.txt"
LOGIN_QRCODE_EXPIRED_TEXT = "二维码已失效"
DATA_URL_RE = re.compile(r"^data:(?P<mime>image/[-+.a-zA-Z0-9]+);base64,(?P<data>.+)$", re.DOTALL)
LAST_UPLOADED_QRCODE_URL: Optional[str] = None


DEBUG = os.getenv("SCUT_MONITOR_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _stderr_print(*args, **kwargs):
    if not DEBUG:
        return None
    kwargs.setdefault("file", sys.stderr)
    kwargs.setdefault("flush", True)
    return builtins.print(*args, **kwargs)


print = _stderr_print


def emit_payload(prefix: str, payload: dict[str, Any]) -> None:
    builtins.print(f"{prefix} {json.dumps(payload, ensure_ascii=False, separators=(',',':'))}", flush=True)



def emit_event(event: str, **kwargs: Any) -> None:
    payload: dict[str, Any] = {"type": "event", "event": event}
    payload.update(kwargs)
    emit_payload("SKILL_EVENT", payload)



def emit_result(ok: bool, command: str, status: str, **kwargs: Any) -> None:
    payload: dict[str, Any] = {
        "type": "result",
        "ok": ok,
        "command": command,
        "status": status,
    }
    payload.update(kwargs)
    emit_payload("SKILL_RESULT", payload)



def current_qrcode_upload_url() -> Optional[str]:
    global LAST_UPLOADED_QRCODE_URL
    if LAST_UPLOADED_QRCODE_URL:
        return LAST_UPLOADED_QRCODE_URL

    url_file = CONFIG.image_upload.url_file
    if url_file.exists():
        value = url_file.read_text(encoding="utf-8").strip()
        if value:
            LAST_UPLOADED_QRCODE_URL = value
            return value
    return None



def build_skill_artifact_summary() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "cookie_file": str(CONFIG.cookie_file),
        "qrcode_image_file": str(LOGIN_QRCODE_IMAGE_FILE),
    }

    upload_url = current_qrcode_upload_url()
    if upload_url:
        payload["qrcode_url"] = upload_url
    if CONFIG.image_upload.url_file.exists():
        payload["qrcode_url_file"] = str(CONFIG.image_upload.url_file)
    if CONFIG.image_upload.response_file.exists():
        payload["qrcode_upload_response_file"] = str(CONFIG.image_upload.response_file)
    return payload


@dataclass
class ImageUploadConfig:
    enabled: bool
    api_url: str
    output_format: str
    cdn_domain: str
    password_enabled: bool
    image_password: str
    request_timeout_seconds: int
    url_file: Path
    response_file: Path


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
    image_upload: ImageUploadConfig


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


def _resolve_optional_path(raw_path: str, fallback_name: str) -> Path:
    path = Path(raw_path or fallback_name)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


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
    cookie_file = _resolve_optional_path(str(merged.get("cookie_file") or "cookies.json"), "cookies.json")

    notify = merged.get("notify") or {}
    image_upload_raw = merged.get("image_upload") or {}
    image_upload = ImageUploadConfig(
        enabled=bool(image_upload_raw.get("enabled", True)),
        api_url=str(image_upload_raw.get("api_url") or DEFAULT_CONFIG["image_upload"]["api_url"]),
        output_format=str(image_upload_raw.get("output_format") or DEFAULT_CONFIG["image_upload"]["output_format"]),
        cdn_domain=str(image_upload_raw.get("cdn_domain") or DEFAULT_CONFIG["image_upload"]["cdn_domain"]),
        password_enabled=bool(image_upload_raw.get("password_enabled", False)),
        image_password=str(image_upload_raw.get("image_password") or ""),
        request_timeout_seconds=int(
            image_upload_raw.get("request_timeout_seconds")
            or DEFAULT_CONFIG["image_upload"]["request_timeout_seconds"]
        ),
        url_file=_resolve_optional_path(
            str(image_upload_raw.get("url_file") or DEFAULT_CONFIG["image_upload"]["url_file"]),
            DEFAULT_CONFIG["image_upload"]["url_file"],
        ),
        response_file=_resolve_optional_path(
            str(image_upload_raw.get("response_file") or DEFAULT_CONFIG["image_upload"]["response_file"]),
            DEFAULT_CONFIG["image_upload"]["response_file"],
        ),
    )

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
        image_upload=image_upload,
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
            emit_event("notify_channel_ok", channel="notify_url")
    except Exception as exc:
        errors.append(f"NOTIFY_URL: {exc}")

    try:
        send_message_via_serverchan(title=title, desp=msg)
        if CONFIG.serverchan_sendkey.strip():
            emit_event("notify_channel_ok", channel="serverchan")
    except Exception as exc:
        errors.append(f"Server酱: {exc}")

    if errors:
        emit_event("notify_channel_error", channels=errors)



def send_notification(old_text: str, new_text: str) -> None:
    emit_event("watch_text_changed", old_text=old_text, new_text=new_text)

    title = "论文盲审状态已更新"
    msg = f"论文盲审状态已更新\n更新前: {old_text}\n更新后: {new_text}"
    send_message(msg, title=title)



def send_session_invalid_notification(
    msg: str = "论文盲审页面对应的教务门户登录态已失效，请尽快重新登录处理。",
) -> None:
    emit_event("session_invalid", reason=msg)
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
            emit_event("browser_installed")
        else:
            raise



def build_browser():
    playwright = sync_playwright().start()
    launch_args = ["--window-size=960,720"]

    try:
        browser = playwright.chromium.launch(
            headless=True,
            args=launch_args,
        )
    except Exception:
        try:
            playwright.stop()
        finally:
            raise

    context = browser.new_context(viewport={"width": 960, "height": 720})
    page = context.new_page()
    return playwright, browser, context, page



def parse_data_url_image(data_url: str) -> tuple[str, bytes]:
    match = DATA_URL_RE.match(data_url.strip())
    if not match:
        raise ValueError("二维码图片 src 不是 data:image/...;base64,... 格式。")

    mime = match.group("mime").lower()
    raw = base64.b64decode(match.group("data"), validate=True)
    return mime, raw



def save_login_qrcode_from_data_url(data_url: str) -> Path:
    mime, raw = parse_data_url_image(data_url)
    if mime != "image/png":
        print(f"检测到二维码 MIME 类型为 {mime}，仍按原始内容写入 {LOGIN_QRCODE_IMAGE_FILE.name}。")

    LOGIN_QRCODE_IMAGE_FILE.write_bytes(raw)
    LOGIN_QRCODE_DATA_FILE.write_text(data_url, encoding="utf-8")
    return LOGIN_QRCODE_IMAGE_FILE



def write_upload_result_files(url: Optional[str], payload: dict[str, Any]) -> None:
    global LAST_UPLOADED_QRCODE_URL
    CONFIG.image_upload.response_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if url:
        CONFIG.image_upload.url_file.write_text(url + "\n", encoding="utf-8")
        LAST_UPLOADED_QRCODE_URL = url
    else:
        LAST_UPLOADED_QRCODE_URL = None
        if CONFIG.image_upload.url_file.exists():
            CONFIG.image_upload.url_file.unlink()



def upload_login_qrcode_if_enabled(image_path: Path) -> Optional[str]:
    upload_cfg = CONFIG.image_upload
    if not upload_cfg.enabled:
        return None

    if upload_cfg.password_enabled and not upload_cfg.image_password:
        raise ValueError("image_upload.password_enabled 为 true 时，image_upload.image_password 不能为空。")

    form_data: dict[str, str] = {}
    output_format = upload_cfg.output_format.strip()
    if output_format:
        form_data["outputFormat"] = output_format

    cdn_domain = upload_cfg.cdn_domain.strip()
    if cdn_domain and cdn_domain.lower() != "default":
        form_data["cdn_domain"] = cdn_domain

    if upload_cfg.password_enabled:
        form_data["password_enabled"] = "true"
        form_data["image_password"] = upload_cfg.image_password

    with image_path.open("rb") as f:
        files = {"image": (image_path.name, f, "image/png")}
        resp = requests.post(
            upload_cfg.api_url,
            files=files,
            data=form_data,
            timeout=upload_cfg.request_timeout_seconds,
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        raise RuntimeError(f"图床返回了非 JSON 响应，HTTP {resp.status_code}") from exc

    if not resp.ok:
        payload.setdefault("http_status", resp.status_code)
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            payload.setdefault("retry_after", retry_after)
        write_upload_result_files(None, payload)
        raise RuntimeError(f"图床上传失败: HTTP {resp.status_code} -> {payload}")

    if not payload.get("success"):
        write_upload_result_files(None, payload)
        raise RuntimeError(f"图床上传失败: {payload}")

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    url = str(data.get("url") or payload.get("url") or "").strip()
    if not url:
        write_upload_result_files(None, payload)
        raise RuntimeError(f"图床响应缺少 url 字段: {payload}")

    write_upload_result_files(url, payload)
    emit_event("login_qrcode_uploaded", qrcode_url=url, qrcode_url_file=str(CONFIG.image_upload.url_file), qrcode_upload_response_file=str(CONFIG.image_upload.response_file))
    return url



def notify_login_qrcode_url_if_possible(upload_url: str) -> None:
    upload_url = str(upload_url or "").strip()
    if not upload_url:
        return

    emit_event("login_qrcode_url_ready", qrcode_url=upload_url, qrcode_url_file=str(CONFIG.image_upload.url_file))

    message = (
        "登录二维码已更新\n"
        f"二维码链接: {upload_url}\n"
        f"本地文件: {LOGIN_QRCODE_IMAGE_FILE.name}"
    )
    send_message(message, title="登录二维码已更新")



def try_export_login_qrcode(page, last_digest: Optional[str]) -> Optional[str]:
    qr_container = page.locator(LOGIN_QRCODE_SELECTOR)
    if qr_container.count() == 0:
        return last_digest

    qr_img = page.locator(LOGIN_QRCODE_IMAGE_SELECTOR).first
    src = qr_img.get_attribute("src")
    if not src:
        return last_digest

    src = src.strip()
    if src.startswith("data:image/"):
        digest = hashlib.sha256(src.encode("utf-8")).hexdigest()
        if digest == last_digest:
            return last_digest

        output_path = save_login_qrcode_from_data_url(src)
        print(f"已提取登录二维码并保存到 {output_path}。")
        emit_event("login_qrcode_exported", qrcode_image_file=str(output_path))
        try:
            upload_url = upload_login_qrcode_if_enabled(output_path)
            if upload_url:
                print(f"已上传二维码到图床: {upload_url}")
                print(f"二维码链接也已写入 {CONFIG.image_upload.url_file}。")
                notify_login_qrcode_url_if_possible(upload_url)
        except Exception as exc:
            emit_event("login_qrcode_upload_failed", error=str(exc), qrcode_image_file=str(output_path))
            print(f"二维码已保存，但上传图床失败: {exc}")
        return digest

    try:
        qr_img.screenshot(path=str(LOGIN_QRCODE_IMAGE_FILE))
        digest = hashlib.sha256(LOGIN_QRCODE_IMAGE_FILE.read_bytes()).hexdigest()
        if digest != last_digest:
            print(f"二维码 src 不是 data URL，已直接截图保存到 {LOGIN_QRCODE_IMAGE_FILE}。")
            emit_event("login_qrcode_exported", qrcode_image_file=str(LOGIN_QRCODE_IMAGE_FILE))
            try:
                upload_url = upload_login_qrcode_if_enabled(LOGIN_QRCODE_IMAGE_FILE)
                if upload_url:
                    print(f"已上传二维码到图床: {upload_url}")
                    print(f"二维码链接也已写入 {CONFIG.image_upload.url_file}。")
                    notify_login_qrcode_url_if_possible(upload_url)
            except Exception as exc:
                emit_event("login_qrcode_upload_failed", error=str(exc), qrcode_image_file=str(LOGIN_QRCODE_IMAGE_FILE))
                print(f"二维码已保存，但上传图床失败: {exc}")
        return digest
    except Exception as exc:
        emit_event("login_qrcode_export_failed", error=str(exc))
        print(f"发现二维码节点，但导出失败: {exc}")
        return last_digest



def refresh_login_page_if_qrcode_expired(page) -> bool:
    expired_locator = page.get_by_text(LOGIN_QRCODE_EXPIRED_TEXT, exact=False).first

    try:
        if expired_locator.count() == 0 or not expired_locator.is_visible():
            return False
    except Exception:
        return False

    emit_event("login_qrcode_expired")
    print(f"检测到“{LOGIN_QRCODE_EXPIRED_TEXT}”，正在刷新页面以重新获取登录二维码。")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(1000)
    return True



def wait_for_manual_login(page) -> None:
    page.goto(CONFIG.portal_url, wait_until="domcontentloaded")
    emit_event("login_waiting", portal_url=CONFIG.portal_url)
    print("请完成扫码登录，出现'研究生教学教务管理系统'后会继续。")

    success_locator = page.locator(f"text={CONFIG.success_text}").first
    last_qrcode_digest: Optional[str] = None

    while True:
        if refresh_login_page_if_qrcode_expired(page):
            last_qrcode_digest = None

        last_qrcode_digest = try_export_login_qrcode(page, last_qrcode_digest)

        try:
            success_locator.wait_for(state="visible", timeout=1000)
            emit_event("login_success")
            print("检测到登录成功。")
            return
        except PlaywrightTimeoutError:
            pass

        page.wait_for_timeout(1000)



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
    emit_event("cookies_saved", cookie_file=str(cookie_file), cookie_count=len(cookies))
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

    emit_event("session_relogin_started", needs_login=True)
    print("准备临时拉起浏览器，等待你手动重新登录。")

    playwright = None
    browser = None
    try:
        ensure_browser_installed()
        playwright, browser, context, page = build_browser()
        print(f"当前固定使用 headless 登录模式，二维码会导出到 {LOGIN_QRCODE_IMAGE_FILE}。")
        wait_for_manual_login(page)
        sync_cookies(context, session)
        save_cookies(context)
        state.session_invalid_notified = False
        emit_event("session_relogin_succeeded", **build_skill_artifact_summary())
        print("已重新获取登录态，浏览器已关闭，继续监控。")
        return True
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        emit_event("session_relogin_failed", error=str(exc))
        print(f"重新登录失败: {exc}")
        if DEBUG:
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
            emit_event("monitor_iteration_error", error=str(exc), error_type=type(exc).__name__)
            if DEBUG:
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
            emit_event("cookie_invalid", cookie_file=str(CONFIG.cookie_file), needs_login=True)
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
        playwright, browser, context, page = build_browser()
        print(f"当前为 headless 登录模式，二维码会导出到 {LOGIN_QRCODE_IMAGE_FILE}。")
        if CONFIG.image_upload.enabled:
            print(f"二维码图床链接会写入 {CONFIG.image_upload.url_file}。")
        wait_for_manual_login(page)
        save_cookies(context)
        emit_result(True, "login", "login_saved", exit_code=0, **build_skill_artifact_summary())
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
        message = "未发现有效 cookie，请先运行 login 子命令。"
        print(message)
        emit_result(False, "check-once", "cookie_missing", exit_code=2, needs_login=True, **build_skill_artifact_summary())
        return 2

    watched_text, resp = fetch_page(session)
    if is_session_invalid(resp, watched_text):
        message = "登录态已失效，请先重新登录。"
        print(message)
        emit_result(False, "check-once", "cookie_invalid", exit_code=3, needs_login=True, **build_skill_artifact_summary())
        return 3

    if watched_text is None:
        message = "XPath 未匹配到目标内容，页面结构可能变化。"
        print(message)
        emit_result(False, "check-once", "xpath_not_found", exit_code=4, watch_xpath=CONFIG.watch_xpath, **build_skill_artifact_summary())
        return 4

    print(watched_text)
    emit_result(True, "check-once", "ok", exit_code=0, watched_text=watched_text, page_url=resp.url, **build_skill_artifact_summary())
    return 0



def run_monitor(interval_seconds: int) -> int:
    state = MonitorState()
    ok, session = validate_or_load_cookie(state)
    if not ok or session is None:
        emit_event("monitor_cookie_missing")
        print("未发现有效 cookie，先进入手动登录流程。")
        login_and_save_cookie()
        ok, session = validate_or_load_cookie(state)
        if not ok or session is None:
            message = "登录后仍无法建立有效会话。"
            print(message)
            emit_result(False, "monitor", "session_not_established", exit_code=2, needs_login=True, interval_seconds=interval_seconds, **build_skill_artifact_summary())
            return 2

    try:
        emit_event("monitor_started", interval_seconds=interval_seconds, initial_text=state.last_text)
        monitor_loop(session, state, interval_seconds)
        emit_result(True, "monitor", "stopped", exit_code=0, interval_seconds=interval_seconds, last_text=state.last_text, **build_skill_artifact_summary())
        return 0
    except KeyboardInterrupt:
        print("\n收到 Ctrl+C，监控退出。")
        emit_result(True, "monitor", "interrupted", exit_code=130, interval_seconds=interval_seconds, last_text=state.last_text, **build_skill_artifact_summary())
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

    try:
        if args.command == "login":
            login_and_save_cookie()
            return 0
        if args.command == "check-once":
            return check_once()
        if args.command == "monitor":
            return run_monitor(interval_seconds=args.interval_seconds)

        parser.error("未知命令")
        return 1
    except KeyboardInterrupt:
        emit_result(False, args.command, "interrupted", exit_code=130, **build_skill_artifact_summary())
        return 130
    except Exception as exc:
        emit_result(False, args.command, "error", exit_code=1, error_type=type(exc).__name__, error=str(exc), **build_skill_artifact_summary())
        if DEBUG:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
