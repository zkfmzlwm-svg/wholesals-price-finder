#!/usr/bin/env python3
"""
도매 최저가 비교 — 웹 버전 서버
================================
데스크탑 앱(wholesale_price_finder_v*.py)의 크롤러·설정·암호화 코드를 그대로
불러와 브라우저 UI(web/static)로 제공한다. 같은 config.json / memo.dat /
암호화 키(~/.wholesale_finder_key)를 공유하므로 데스크탑 앱과 번갈아 써도 된다.

실행:
  pip install -r requirements.txt
  python web/server.py              → http://127.0.0.1:8000 자동으로 열림

옵션 (환경변수 또는 인자):
  --host / WPF_HOST          기본 127.0.0.1 (이 PC에서만 접속)
  --port / WPF_PORT          기본 8000
  --password / WPF_WEB_PASSWORD
                             설정 시 접속 비밀번호 요구 (외부 공개·서버 배포 시 필수)
  --data-dir / WPF_DATA_DIR  config.json/memo.dat/debug 저장 폴더
                             (기본: 데스크탑 앱과 같은 폴더)
  --no-browser               시작 시 브라우저 자동 열기 안 함
"""
import argparse, asyncio, hashlib, hmac, importlib.util, json, os, re, sys, threading, types, webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from aiohttp import web

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"


# ═══════════════════════════════════════════════════════════════
# 1. 데스크탑 앱 모듈 불러오기 (크롤러/설정/암호화 공유)
# ═══════════════════════════════════════════════════════════════
def _version_key(p: Path):
    m = re.search(r"_v([\d.]+)\.py$", p.name)
    return tuple(int(x) for x in m.group(1).split(".") if x) if m else ()

def _install_tk_stub():
    """서버에는 보통 tkinter가 없음. 데스크탑 파일은 import 시점에 GUI 클래스만
    정의하고 실행은 __main__에서만 하므로, 빈 껍데기 모듈이면 충분하다."""
    try:
        import tkinter  # noqa: F401
        return
    except ImportError:
        pass
    tk = types.ModuleType("tkinter")
    for name in ("Tk", "Toplevel", "Frame", "Menu"):
        setattr(tk, name, type(name, (), {}))
    ttk = types.ModuleType("tkinter.ttk")
    mb = types.ModuleType("tkinter.messagebox")
    tk.ttk, tk.messagebox = ttk, mb
    sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk, "tkinter.messagebox": mb})

def load_core():
    candidates = sorted(ROOT.glob("wholesale_price_finder_v*.py"), key=_version_key)
    if not candidates:
        raise SystemExit(f"데스크탑 앱 파일(wholesale_price_finder_v*.py)을 찾을 수 없습니다: {ROOT}")
    _install_tk_stub()
    path = candidates[-1]
    spec = importlib.util.spec_from_file_location("wpf_core", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

core = load_core()


def apply_data_dir(data_dir: str):
    if not data_dir:
        return
    d = Path(data_dir).expanduser().resolve()
    d.mkdir(parents=True, exist_ok=True)
    core.CONFIG_PATH = d / "config.json"
    core.MEMO_PATH = d / "memo.dat"
    core.DEBUG_DIR = d / "debug"


# 설정 파일은 요청마다 새로 읽고 저장한다 (데스크탑 앱이 동시에 수정해도 최신값 사용).
_config_lock = asyncio.Lock()

MEMO_TEMPLATE = (
    "═══ 사이트별 로그인 정보 ═══\n\n"
    "▶ 바로팜\n  아이디: \n  비밀번호: \n\n"
    "▶ 유팜몰\n  아이디: \n  비밀번호: \n\n"
    "▶ 한미몰\n  아이디: \n  비밀번호: \n\n"
    "▶ 플랫팜\n  아이디: \n  비밀번호: \n\n"
    "▶ 새로팜\n  아이디: \n  비밀번호: \n\n"
    "═══ 기타 메모 ═══\n\n"
)


# ═══════════════════════════════════════════════════════════════
# 2. 직렬화 헬퍼
# ═══════════════════════════════════════════════════════════════
def site_open_url(site_name: str, name: str, fallback: str = "") -> str:
    """더블클릭/우클릭 '사이트에서 검색' 주소 — 데스크탑 _open_product_search_by_idx와 동일"""
    pattern = core.SITE_SEARCH_PATTERNS.get(site_name, "")
    url = pattern.replace("{query}", quote(name)) if pattern else fallback
    return url if url.startswith("http") else ""

def public_site(site: dict, idx: int) -> dict:
    """비밀번호(암호문 포함)는 내보내지 않고 저장 여부·마스킹만 전달"""
    creds = site.get("credentials", {})
    has_pw = bool(creds.get("password_encrypted"))
    lc = site.get("login_config", {}) or {}
    fields = list((lc.get("login_fields") or {}).keys())
    sel = site.get("selectors", {}) or {}
    return {
        "idx": idx,
        "name": site.get("name", ""),
        "base_url": site.get("base_url", ""),
        "crawler_type": site.get("crawler_type", "generic"),
        "requires_login": bool(site.get("requires_login")),
        "enabled": site.get("enabled", True),
        "builtin": bool(site.get("builtin")),
        "builtin_id": site.get("builtin_id"),
        "username": creds.get("username", ""),
        "has_password": has_pw,
        "password_masked": core.cred_mgr.mask(core.get_site_password(site)) if has_pw else "",
        "login_url": lc.get("login_url", "/member/login"),
        "id_field": fields[0] if fields else "user_id",
        "pw_field": fields[1] if len(fields) > 1 else "password",
        "selectors": {k: sel.get(k, d) for k, d in (
            ("search_url_pattern", "/search?q={query}"),
            ("product_list", ".product-item"),
            ("product_name", ".product-name"),
            ("product_price", ".product-price"),
        )},
    }

def product_dict(p) -> dict:
    d = p.to_dict()
    d["maker"] = (p.extra_info or {}).get("제조사", "")
    d["open_url"] = site_open_url(p.site_name, p.name, p.url)
    return d

def favorite_dict(f: dict, idx: int) -> dict:
    d = dict(f)
    d["idx"] = idx
    d["open_url"] = site_open_url(f.get("site_name", ""), f.get("name", ""), f.get("url", ""))
    return d

def bad_request(msg: str, status: int = 400):
    return web.json_response({"error": msg}, status=status)

def site_index(request, config):
    try:
        idx = int(request.match_info["idx"])
    except ValueError:
        return None
    return idx if 0 <= idx < len(config.get("sites", [])) else None


# ═══════════════════════════════════════════════════════════════
# 3. API 핸들러
# ═══════════════════════════════════════════════════════════════
routes = web.RouteTableDef()

@routes.get("/api/info")
async def api_info(request):
    return web.json_response({
        "version": core.__version__,
        "encryption": core.cred_mgr.method,
        "config_path": str(core.CONFIG_PATH),
        "crawler_types": ["generic", "demo"] + list(core.CUSTOM_CRAWLERS.keys()),
        "auth_required": bool(request.app["password"]),
    })

@routes.get("/api/state")
async def api_state(request):
    config = core.load_config()
    return web.json_response({
        "sites": [public_site(s, i) for i, s in enumerate(config.get("sites", []))],
        "favorites": [favorite_dict(f, i) for i, f in enumerate(config.get("favorites", []))],
        "settings": config.get("settings", {}),
    })

# ──────── 검색 ────────
@routes.post("/api/search")
async def api_search(request):
    body = await request.json()
    query = (body.get("query") or "").strip()
    if not query:
        return bad_request("검색어를 입력하세요")
    config = core.load_config()
    sites = [s for s in config.get("sites", []) if s.get("enabled", True)]
    if not sites:
        return bad_request("활성 사이트가 없습니다. '사이트 관리' 탭에서 사이트를 추가하세요.")
    results = await core.search_all(query, config)
    return web.json_response({
        "query": query,
        "results": [{
            "site_name": r.site_name,
            "error": r.error,
            "elapsed_sec": r.elapsed_sec,
            "products": [product_dict(p) for p in r.products],
        } for r in results],
    })

# ──────── 설정 ────────
@routes.put("/api/settings")
async def api_settings(request):
    body = await request.json()
    async with _config_lock:
        config = core.load_config()
        st = config.setdefault("settings", {})
        try:
            if "max_results_per_site" in body:
                st["max_results_per_site"] = int(body["max_results_per_site"])
            if "timeout_seconds" in body:
                st["timeout_seconds"] = int(body["timeout_seconds"])
        except (TypeError, ValueError):
            return bad_request("숫자를 입력하세요")
        if "hide_soldout" in body:
            st["hide_soldout"] = bool(body["hide_soldout"])
        if body.get("sort_by") in ("price", "name"):
            st["sort_by"] = body["sort_by"]
        core.save_config(config)
    return web.json_response({"settings": st})

# ──────── 즐겨찾기 ────────
@routes.post("/api/favorites")
async def api_add_favorite(request):
    p = await request.json()
    async with _config_lock:
        config = core.load_config()
        favs = config.setdefault("favorites", [])
        for f in favs:  # 중복 확인 (같은 사이트 + 이름)
            if f.get("site_name") == p.get("site_name") and f.get("name") == p.get("name"):
                return bad_request(f"'{(p.get('name') or '')[:30]}' 이미 즐겨찾기에 있습니다.", 409)
        favs.append({
            "site_name": p.get("site_name", ""),
            "name": p.get("name", ""),
            "price": int(p.get("price") or 0),
            "unit_price": p.get("unit_price") or "",
            "maker": p.get("maker", ""),
            "url": p.get("url", ""),
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        core.save_config(config)
    return web.json_response({"ok": True})

@routes.delete("/api/favorites/{idx}")
async def api_delete_favorite(request):
    async with _config_lock:
        config = core.load_config()
        favs = config.get("favorites", [])
        try:
            idx = int(request.match_info["idx"])
        except ValueError:
            return bad_request("잘못된 항목")
        if not 0 <= idx < len(favs):
            return bad_request("항목을 찾을 수 없습니다", 404)
        favs.pop(idx)
        core.save_config(config)
    return web.json_response({"ok": True})

# ──────── 사이트 관리 ────────
def build_site(form: dict, old: dict = None) -> dict:
    """데스크탑 SiteDialog._save와 같은 규칙으로 사이트 설정을 만든다."""
    site = json.loads(json.dumps(core.SITE_TEMPLATE))
    site["name"] = (form.get("name") or "").strip()
    site["base_url"] = (form.get("base_url") or "").strip()
    site["crawler_type"] = form.get("crawler_type") or "generic"
    site["requires_login"] = bool(form.get("requires_login"))

    if site["requires_login"]:
        site["credentials"]["username"] = (form.get("username") or "").strip()
        pw = form.get("password") or ""
        if pw:
            site["credentials"]["password_encrypted"] = core.cred_mgr.encrypt(pw)
        elif old is not None:  # 비밀번호 미변경 → 기존 유지
            site["credentials"]["password_encrypted"] = old.get("credentials", {}).get("password_encrypted", "")
        site["login_config"]["login_url"] = form.get("login_url") or "/member/login"
        site["login_config"]["login_fields"] = {
            form.get("id_field") or "user_id": "{username}",
            form.get("pw_field") or "password": "{password}",
        }

    for key, val in (form.get("selectors") or {}).items():
        if key in site["selectors"]:
            site["selectors"][key] = val

    if old is not None:  # 수정 — 기존의 enabled 상태 및 builtin 표시 유지
        site["enabled"] = old.get("enabled", True)
        if old.get("builtin"):
            site["builtin"] = True
            if old.get("builtin_id"):
                site["builtin_id"] = old["builtin_id"]
    if "enabled" in form:
        site["enabled"] = bool(form["enabled"])
    return site

@routes.put("/api/sites/{idx}")
async def api_edit_site(request):
    form = await request.json()
    if not (form.get("name") or "").strip() or not (form.get("base_url") or "").strip():
        return bad_request("사이트 이름과 URL은 필수입니다")
    async with _config_lock:
        config = core.load_config()
        idx = site_index(request, config)
        if idx is None:
            return bad_request("사이트를 찾을 수 없습니다", 404)
        config["sites"][idx] = build_site(form, config["sites"][idx])
        core.save_config(config)
    return web.json_response({"ok": True})

@routes.put("/api/sites/{idx}/enabled")
async def api_toggle_site(request):
    body = await request.json()
    async with _config_lock:
        config = core.load_config()
        idx = site_index(request, config)
        if idx is None:
            return bad_request("사이트를 찾을 수 없습니다", 404)
        config["sites"][idx]["enabled"] = bool(body.get("enabled"))
        core.save_config(config)
    return web.json_response({"ok": True})

@routes.put("/api/sites/{idx}/credentials")
async def api_credentials(request):
    """데스크탑 CredentialDialog._save와 동일 — 빈 칸은 기존값 유지"""
    body = await request.json()
    async with _config_lock:
        config = core.load_config()
        idx = site_index(request, config)
        if idx is None:
            return bad_request("사이트를 찾을 수 없습니다", 404)
        site = config["sites"][idx]
        user = (body.get("username") or "").strip()
        pw = body.get("password") or ""
        if user:
            site.setdefault("credentials", {})["username"] = user
        if pw:
            site.setdefault("credentials", {})["password_encrypted"] = core.cred_mgr.encrypt(pw)
        site["requires_login"] = bool(user)
        core.save_config(config)
    return web.json_response({"ok": True, "encryption": core.cred_mgr.method})

@routes.delete("/api/sites/{idx}")
async def api_delete_site(request):
    async with _config_lock:
        config = core.load_config()
        idx = site_index(request, config)
        if idx is None:
            return bad_request("사이트를 찾을 수 없습니다", 404)
        config["sites"].pop(idx)
        core.save_config(config)
    return web.json_response({"ok": True})

async def _login_one(site: dict) -> dict:
    name = site.get("name", "")
    try:
        crawler = core.create_crawler(site)
        try:
            await crawler.login()
            if crawler.logged_in:
                return {"site_name": name, "ok": True, "message": "로그인 성공"}
            return {"site_name": name, "ok": False, "message": "로그인 실패"}
        finally:
            await crawler.close()
    except Exception as ex:
        return {"site_name": name, "ok": False, "message": str(ex)}

@routes.post("/api/login-test")
async def api_login_test(request):
    config = core.load_config()
    login_sites = [s for s in config.get("sites", []) if s.get("credentials", {}).get("username")]
    if not login_sites:
        return bad_request("로그인 정보가 설정된 사이트가 없습니다. '🔑 로그인 설정'으로 먼저 설정하세요.")
    results = await asyncio.gather(*[_login_one(s) for s in login_sites])
    return web.json_response({"results": list(results)})

@routes.post("/api/demo")
async def api_load_demo(request):
    """데스크탑 _load_demo와 동일 — 내장 사이트(로그인 정보 유지) + 데모 2개"""
    import copy
    async with _config_lock:
        config = core.load_config()
        builtin = [copy.deepcopy(s) for s in core.BUILTIN_SITES]
        demos = [{
            "name": n, "enabled": True, "crawler_type": "demo",
            "base_url": u, "requires_login": True,
            "credentials": {"username": "demo", "password_encrypted": core.cred_mgr.encrypt("demo")},
            "login_config": core.SITE_TEMPLATE["login_config"].copy(), "selectors": {}, "extra_config": {},
        } for n, u in (("데모도매A", "https://demo-a.example.com"), ("데모도매B", "https://demo-b.example.com"))]
        for bs in builtin:
            for existing in config.get("sites", []):
                if existing.get("builtin_id") == bs["builtin_id"]:
                    bs["credentials"] = existing.get("credentials", bs["credentials"])
                    break
        config["sites"] = builtin + demos
        core.save_config(config)
    return web.json_response({"ok": True})

# ──────── 메모장 (암호화 저장) ────────
@routes.get("/api/memo")
async def api_get_memo(request):
    content = ""
    if core.MEMO_PATH.exists():
        try:
            content = core.cred_mgr.decrypt(core.MEMO_PATH.read_text(encoding="utf-8"))
        except Exception:
            content = ""
    return web.json_response({"content": content or MEMO_TEMPLATE, "saved": bool(content)})

@routes.put("/api/memo")
async def api_put_memo(request):
    body = await request.json()
    try:
        core.MEMO_PATH.write_text(core.cred_mgr.encrypt(body.get("content", "")), encoding="utf-8")
    except Exception as e:
        return bad_request(f"메모 저장 중 오류: {e}", 500)
    return web.json_response({"ok": True, "encryption": core.cred_mgr.method})

# ──────── 진단 파일(debug/) ────────
@routes.get("/api/debug")
async def api_debug_list(request):
    d = core.DEBUG_DIR
    files = []
    if d.exists():
        for p in sorted(d.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.is_file():
                st = p.stat()
                files.append({"name": p.name, "size": st.st_size,
                              "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")})
    return web.json_response({"dir": str(d), "files": files})

def _debug_path(request):
    name = request.match_info["name"]
    p = (core.DEBUG_DIR / name).resolve()
    if p.parent != core.DEBUG_DIR.resolve() or not p.is_file():
        return None
    return p

@routes.get("/api/debug/{name}")
async def api_debug_get(request):
    p = _debug_path(request)
    if not p:
        return bad_request("파일을 찾을 수 없습니다", 404)
    return web.FileResponse(p, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(p.name)}"})

@routes.delete("/api/debug/{name}")
async def api_debug_delete(request):
    p = _debug_path(request)
    if not p:
        return bad_request("파일을 찾을 수 없습니다", 404)
    p.unlink()
    return web.json_response({"ok": True})

# ──────── 접속 비밀번호 (선택) ────────
def _token(password: str) -> str:
    return hmac.new(password.encode(), b"wpf-web-session", hashlib.sha256).hexdigest()

@routes.post("/api/auth")
async def api_auth(request):
    pw = request.app["password"]
    body = await request.json()
    if not pw:
        return web.json_response({"ok": True})
    if not hmac.compare_digest(body.get("password", ""), pw):
        return bad_request("비밀번호가 틀렸습니다", 401)
    resp = web.json_response({"ok": True})
    resp.set_cookie("wpf_token", _token(pw), httponly=True, samesite="Strict", max_age=60 * 60 * 24 * 30)
    return resp

@web.middleware
async def auth_middleware(request, handler):
    pw = request.app["password"]
    path = request.path
    if pw and path.startswith("/api/") and path not in ("/api/auth", "/api/info"):
        if not hmac.compare_digest(request.cookies.get("wpf_token", ""), _token(pw)):
            return bad_request("접속 비밀번호가 필요합니다", 401)
    try:
        return await handler(request)
    except json.JSONDecodeError:
        return bad_request("잘못된 요청 형식")

@routes.get("/")
async def index(request):
    return web.FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


# ═══════════════════════════════════════════════════════════════
# 4. 실행
# ═══════════════════════════════════════════════════════════════
def make_app(password: str = "") -> web.Application:
    app = web.Application(middlewares=[auth_middleware], client_max_size=4 * 1024 ** 2)
    app["password"] = password
    app.add_routes(routes)
    app.router.add_static("/static/", STATIC_DIR)
    return app

def main():
    ap = argparse.ArgumentParser(description="도매 최저가 비교 — 웹 버전")
    ap.add_argument("--host", default=os.environ.get("WPF_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("WPF_PORT", "8000")))
    ap.add_argument("--password", default=os.environ.get("WPF_WEB_PASSWORD", ""))
    ap.add_argument("--data-dir", default=os.environ.get("WPF_DATA_DIR", ""))
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    apply_data_dir(args.data_dir)
    if args.host not in ("127.0.0.1", "localhost", "::1") and not args.password:
        print("⚠ 외부 접속을 허용하면서 접속 비밀번호가 없습니다. --password 또는 WPF_WEB_PASSWORD를 설정하세요.")

    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '::') else args.host}:{args.port}"
    print(f"도매 최저가 비교 v{core.__version__} (웹) — {url}")
    print(f"설정 파일: {core.CONFIG_PATH}  |  암호화: {core.cred_mgr.method}")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    web.run_app(make_app(args.password), host=args.host, port=args.port, print=None)

if __name__ == "__main__":
    main()
