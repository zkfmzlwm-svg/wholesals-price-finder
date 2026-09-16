#!/usr/bin/env python3
"""
도매 최저가 비교 프로그램 v2.0 — Windows GUI
=============================================
tkinter 기반 데스크탑 프로그램. 파이썬만 설치되어 있으면 별도 설치 없이 실행 가능.
PyInstaller로 exe 변환 가능: pyinstaller --onefile --windowed wholesale_price_finder_v2.0.py

필요 패키지:
  pip install aiohttp beautifulsoup4
  pip install cryptography   (선택 — 비밀번호 강력 암호화)

버전 정책 (v1.0부터 적용):
  - 기능 추가/변경 → 정수 버전업 (예: 1.0 → 2.0)
  - 사이트 추가     → 소수점 버전업 (예: 1.0 → 1.1)

변경 이력:
  v2.2 — 대웅더샵(the.shop.co.kr / www.shop.co.kr) 로그인·검색 요청 형식 일부
         확인. 로그인 POST https://www.shop.co.kr/front/front/api/auth/login
         (필드 userId/userPwd, 페이로드가 JSON인지 form-urlencoded인지는 미확인),
         검색 GET https://the.shop.co.kr/contents/search?searchKey=all&
         searchVal={query} (Next.js SSR 풀 페이지 HTML에 상품 리스트가 직접
         렌더링됨을 확인). 단, 상품 목록 HTML의 정확한 CSS 셀렉터는 아직
         미확인이라 generic 크롤러 selectors는 여전히 placeholder임.
  v2.1 — 스마트팜(smartpharm.co.kr) 로그인/검색/상품목록 파싱 형식 확인, 전용
         SmartPharmCrawler로 완성. 로그인 POST /Login/Login.asp(UserID/UserPW
         평문, 암호화 없음), 검색 GET /Goods/Goods_List.asp(TopSearchKey는
         EUC-KR 인코딩 필수, TopSearch_CMP_NUM=0002 고정값), 목록 파싱은
         tr#GoodsTR 행에서 a.list(상품명)/td.smart_nomal(규격,제조사)/
         td.smart_money2(공급가)를 읽고 onclick 속성의 iPageGo(...Key=XXXX...)
         에서 상세 페이지 Key를 추출.
  v2.0 — 검색 결과 화면에 사이트별 결과 건수 표시 추가 (0건/오류인 사이트를
         검색할 때마다 바로 확인 가능 — 사이트 HTML 구조 변경으로 파싱이
         조용히 깨지는 문제를 사용자가 즉시 알아챌 수 있도록 함).
         바로팜 로그인 API 주소 변경(404) 및 팜스트리트 로그인 판정 로직
         (AJAX/JSON 응답 기준) 수정.
  v1.4 — 사이트 4곳 추가(대웅더샵/동아DAPmall/서울약사신협/스마트팜, generic 크롤러).
         샌드박스 네트워크 제한으로 실제 로그인/검색 응답을 확인하지 못해 로그인
         URL·필드명·검색 셀렉터는 placeholder임. "사이트 관리 > 수정"에서 실제
         값으로 보정 필요.
  v1.0 — 버전 넘버링 재시작 기준판. 8개 사이트(바로팜/유팜몰/한미몰/플랫팜/새로팜/
         팜뉴트리션/드시모네/팜스트리트) + 즐겨찾기/메모장/암호화 기능 포함.
         전체 디버그: Generic 크롤러 검색어 URL 인코딩 누락, 사이트 수정 시
         내장(builtin) 표시 소실, 미사용 import 제거.
"""

__version__ = "2.2"

# ═══════════════════════════════════════════════════════════════
# 표준 라이브러리
# ═══════════════════════════════════════════════════════════════
import json, re, sys, asyncio, time, random, base64, threading, webbrowser
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict
from abc import ABC, abstractmethod
from urllib.parse import quote
from yarl import URL as YarlURL

import tkinter as tk
from tkinter import ttk, messagebox

# ═══════════════════════════════════════════════════════════════
# 외부 패키지
# ═══════════════════════════════════════════════════════════════
try:
    import aiohttp
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp", "beautifulsoup4"])
    import aiohttp
    from bs4 import BeautifulSoup


# ═══════════════════════════════════════════════════════════════
# 1. 비밀번호 암호화
# ═══════════════════════════════════════════════════════════════
class CredentialManager:
    KEY_FILE = Path.home() / ".wholesale_finder_key"

    def __init__(self):
        self._fernet = None
        try:
            from cryptography.fernet import Fernet
            key = self._load_or_create_key()
            self._fernet = Fernet(key)
            self.method = "AES (Fernet)"
        except ImportError:
            self.method = "Base64"

    def _load_or_create_key(self) -> bytes:
        from cryptography.fernet import Fernet
        if self.KEY_FILE.exists():
            return self.KEY_FILE.read_bytes().strip()
        key = Fernet.generate_key()
        self.KEY_FILE.write_bytes(key)
        try:
            self.KEY_FILE.chmod(0o600)
        except Exception:
            pass
        return key

    def encrypt(self, plain: str) -> str:
        if not plain:
            return ""
        if self._fernet:
            return "ENC:FERNET:" + self._fernet.encrypt(plain.encode()).decode()
        return "ENC:B64:" + base64.b64encode(plain.encode()).decode()

    def decrypt(self, cipher: str) -> str:
        if not cipher:
            return ""
        if not cipher.startswith("ENC:"):
            return cipher
        if cipher.startswith("ENC:FERNET:"):
            token = cipher[len("ENC:FERNET:"):]
            if self._fernet:
                return self._fernet.decrypt(token.encode()).decode()
            raise ValueError("cryptography 패키지 필요")
        if cipher.startswith("ENC:B64:"):
            return base64.b64decode(cipher[len("ENC:B64:"):]).decode()
        return cipher

    def mask(self, plain: str) -> str:
        if not plain:
            return ""
        return plain[:1] + "•" * min(len(plain) - 1, 8)

cred_mgr = CredentialManager()


# ═══════════════════════════════════════════════════════════════
# 2. 데이터 모델
# ═══════════════════════════════════════════════════════════════
@dataclass
class Product:
    name: str
    price: int
    unit_price: Optional[str]
    url: str
    site_name: str
    image_url: Optional[str] = None
    min_order_qty: Optional[int] = None
    shipping_fee: Optional[int] = None
    in_stock: bool = True
    extra_info: dict = field(default_factory=dict)

    @property
    def total_cost(self) -> int:
        return self.price + (self.shipping_fee or 0)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_cost"] = self.total_cost
        return d

@dataclass
class SearchResult:
    site_name: str
    query: str
    products: list
    searched_at: str = ""
    error: Optional[str] = None
    elapsed_sec: float = 0.0
    def __post_init__(self):
        if not self.searched_at:
            self.searched_at = datetime.now().isoformat()


# ═══════════════════════════════════════════════════════════════
# 3. 설정 관리
# ═══════════════════════════════════════════════════════════════
CONFIG_PATH = Path(__file__).parent / "config.json"
MEMO_PATH = Path(__file__).parent / "memo.dat"

# 사이트별 상품명 검색 URL 패턴 (더블클릭/우클릭 검색용)
SITE_SEARCH_PATTERNS = {
    "바로팜":  "https://www.baropharm.com/order?q={query}",
    "유팜몰":  "https://www.upharmmall.co.kr/Search/Search.aspx?keyword={query}",
    "한미몰":  "https://hmpmall.co.kr/search/searchTwoStepList.do?productName={query}",
    "플랫팜":  "https://www.platpharm.co.kr/search?qs={query}",
    "새로팜":  "https://www.saeropharm.com/w/product/searchProductList.do?mainSchValue={query}",
}

DEFAULT_CONFIG = {
    "version": __version__,
    "sites": [],  # 초기 실행 시 BUILTIN_SITES 자동 추가
    "favorites": [],
    "settings": {
        "max_results_per_site": 10,
        "timeout_seconds": 30,
        "sort_by": "price",
    },
}

SITE_TEMPLATE = {
    "name": "", "enabled": True, "crawler_type": "generic",
    "base_url": "", "requires_login": False,
    "credentials": {"username": "", "password_encrypted": ""},
    "login_config": {
        "login_url": "/member/login", "login_method": "form_post",
        "login_fields": {"user_id": "{username}", "password": "{password}"},
        "csrf_selector": None, "csrf_field_name": None,
        "login_check_url": None, "login_check_selector": None, "login_check_text": None,
    },
    "selectors": {
        "search_url_pattern": "/search?q={query}",
        "product_list": ".product-item", "product_name": ".product-name",
        "product_price": ".product-price", "product_link": "a[href]", "product_image": "img",
    },
    "extra_config": {},
}

def load_config() -> dict:
    import copy
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        migrated = False
        for site in config.get("sites", []):
            creds = site.get("credentials", {})
            if "password" in creds and "password_encrypted" not in creds:
                plain = creds.pop("password")
                creds["password_encrypted"] = cred_mgr.encrypt(plain) if plain else ""
                migrated = True
            if "login_config" not in site:
                site["login_config"] = SITE_TEMPLATE["login_config"].copy()
                site["requires_login"] = bool(creds.get("username"))
                migrated = True
        # 내장 사이트가 빠져 있으면 자동 추가
        # (이름 기준 매칭 — 여러 내장 사이트가 같은 crawler_type("generic")을
        #  공유할 수 있으므로 crawler_type만으로는 개별 사이트 누락을 못 잡음)
        existing_names = {s.get("name") for s in config.get("sites", [])}
        for builtin in BUILTIN_SITES:
            if builtin["name"] not in existing_names:
                config.setdefault("sites", []).insert(0, copy.deepcopy(builtin))
                migrated = True
        if migrated:
            save_config(config)
        # favorites 키 없으면 추가 (구버전 호환)
        if "favorites" not in config:
            config["favorites"] = []
        return config
    # 최초 실행: 내장 사이트 포함된 기본 설정 생성
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    config["sites"] = [copy.deepcopy(s) for s in BUILTIN_SITES]
    save_config(config)
    return config

def save_config(config: dict):
    config["version"] = __version__
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_site_password(site: dict) -> str:
    enc = site.get("credentials", {}).get("password_encrypted", "")
    if not enc:
        return ""
    try:
        return cred_mgr.decrypt(enc)
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════
# 4. 크롤러
# ═══════════════════════════════════════════════════════════════
class LoginError(Exception):
    pass

class BaseCrawler(ABC):
    def __init__(self, site_config: dict):
        self.config = site_config
        self.base_url = site_config.get("base_url", "").rstrip("/")
        self.credentials = site_config.get("credentials", {})
        self.login_config = site_config.get("login_config", {})
        self.selectors = site_config.get("selectors", {})
        self.site_name = site_config.get("name", "Unknown")
        self.session: Optional[aiohttp.ClientSession] = None
        self.logged_in = False
        self._csrf_token = None
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9",
        }

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers=self._headers,
                cookie_jar=aiohttp.CookieJar(unsafe=True),
                timeout=aiohttp.ClientTimeout(total=30),
            )

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_html(self, url):
        await self._ensure_session()
        async with self.session.get(url) as r:
            r.raise_for_status(); return await r.text()

    async def get_soup(self, url):
        return BeautifulSoup(await self.get_html(url), "html.parser")

    async def post_form(self, url, data):
        await self._ensure_session()
        async with self.session.post(url, data=data) as r:
            await r.text(); return r

    async def _fetch_csrf(self):
        sel = self.login_config.get("csrf_selector")
        if not sel: return None
        soup = await self.get_soup(self.full_url(self.login_config.get("login_url", "")))
        el = soup.select_one(sel)
        if el: self._csrf_token = el.get("value", "")
        return self._csrf_token

    async def login(self):
        username = self.credentials.get("username", "")
        if not username: return
        password = get_site_password(self.config)
        if not password:
            raise LoginError(f"'{self.site_name}' 비밀번호 미설정")
        await self._fetch_csrf()
        login_url = self.full_url(self.login_config.get("login_url", "/member/login"))
        fields = self.login_config.get("login_fields", {})
        data = {k: v.replace("{username}", username).replace("{password}", password) for k, v in fields.items()}
        csrf_field = self.login_config.get("csrf_field_name")
        if csrf_field and self._csrf_token:
            data[csrf_field] = self._csrf_token
        await self.post_form(login_url, data)
        if not await self.verify_login():
            raise LoginError(f"'{self.site_name}' 로그인 실패")
        self.logged_in = True

    async def verify_login(self) -> bool:
        cu = self.login_config.get("login_check_url")
        if cu:
            try:
                html = await self.get_html(self.full_url(cu))
                cs = self.login_config.get("login_check_selector")
                if cs: return BeautifulSoup(html, "html.parser").select_one(cs) is not None
                ct = self.login_config.get("login_check_text")
                if ct: return ct in html
                return True
            except: return False
        await self._ensure_session()
        return len(self.session.cookie_jar.filter_cookies(YarlURL(self.base_url))) > 0

    @staticmethod
    def extract_price(text):
        if not text: return 0
        c = re.sub(r"[^\d]", "", text)
        return int(c) if c else 0

    @staticmethod
    def clean_text(text):
        return re.sub(r"\s+", " ", text).strip() if text else ""

    def full_url(self, path):
        if not path: return self.base_url
        if path.startswith("http"): return path
        return f"{self.base_url}/{path.lstrip('/')}"

    @abstractmethod
    async def search(self, query, max_results=10) -> list: ...


class GenericCrawler(BaseCrawler):
    async def search(self, query, max_results=10):
        pat = self.selectors.get("search_url_pattern", "/search?q={query}")
        soup = await self.get_soup(self.full_url(pat.replace("{query}", quote(query))))
        sel = self.selectors
        products = []
        for item in soup.select(sel.get("product_list", ".product-item"))[:max_results]:
            try:
                ne = item.select_one(sel.get("product_name", ".product-name"))
                pe = item.select_one(sel.get("product_price", ".product-price"))
                le = item.select_one(sel.get("product_link", "a[href]"))
                if not (ne and pe): continue
                products.append(Product(
                    name=self.clean_text(ne.get_text()), price=self.extract_price(pe.get_text()),
                    unit_price=None, url=self.full_url(le["href"]) if le else "",
                    site_name=self.site_name,
                ))
            except: continue
        products.sort(key=lambda p: p.price)
        return products


class DemoCrawler(BaseCrawler):
    DEMO_DB = {
        "장갑": [("니트릴 장갑 100매 (M)", 8500, 15200, "100매당 8,500원"), ("라텍스 장갑 100매 (L)", 7200, 13800, "100매당 7,200원"),
                ("비닐 장갑 500매", 4500, 8900, "100매당 900원"), ("면 장갑 10켤레", 3200, 6500, "1켤레당 320원")],
        "마스크": [("KF94 마스크 50매", 15000, 28000, "1매당 300원"), ("KF80 마스크 100매", 12000, 22000, "1매당 120원"),
                 ("덴탈 마스크 200매", 9800, 18500, "1매당 49원"), ("3중 필터 마스크 50매", 6500, 12000, "1매당 130원")],
        "소독제": [("에탄올 소독제 4L", 18000, 32000, "1L당 4,500원"), ("손 소독제 500ml x 12", 24000, 42000, "1개당 2,000원"),
                 ("살균 소독 티슈 100매 x 10", 15500, 28000, "1매당 15.5원"), ("차아염소산 소독수 20L", 22000, 38000, "1L당 1,100원")],
    }
    async def login(self): self.logged_in = True
    async def verify_login(self): return True
    async def search(self, query, max_results=10):
        matched = next((v for k, v in self.DEMO_DB.items() if k in query), None)
        if not matched: matched = [("일반 상품 A", 5000, 9500, None), ("일반 상품 B", 8000, 15000, None)]
        products = []
        for name, lo, hi, up in matched[:max_results]:
            products.append(Product(name=name, price=random.randint(lo, hi), unit_price=up,
                url=f"{self.base_url}/product/{random.randint(10000,99999)}", site_name=self.site_name,
                shipping_fee=random.choice([0, 0, 2500, 3000]), in_stock=random.random() > 0.1,
                min_order_qty=random.choice([None, 1, 5, 10])))
        products.sort(key=lambda p: p.price)
        return products

class BaroPharmCrawler(BaseCrawler):
    """
    바로팜 (baropharm.com) 전용 크롤러.

    로그인: POST https://api-v2.baropharm.com/auth/login (2026-09 확인, 구 주소는 404)
            payload: {"username": "...", "password": "..."}
            응답: {"key": "토큰값"} → 이후 요청에 Authorization: Token <key> 헤더

    검색:   GET https://api-v2.baropharm.com/me/search/products?q=검색어
            응답: {"products": [{"name": "...", "items": [{"lowest_price": ..., ...}]}]}
    """

    API_LOGIN   = "https://api-v2.baropharm.com/auth/login"
    API_SEARCH  = "https://api-v2.baropharm.com/me/search/products"
    WEB_PRODUCT = "https://www.baropharm.com/order?q="

    def __init__(self, site_config: dict):
        super().__init__(site_config)
        self._token = None

    async def login(self):
        username = self.credentials.get("username", "")
        if not username:
            return
        password = get_site_password(self.config)
        if not password:
            raise LoginError(f"'{self.site_name}' 비밀번호 미설정")

        await self._ensure_session()
        async with self.session.post(
            self.API_LOGIN,
            json={"username": username, "password": password},
            headers={**self._headers, "Content-Type": "application/json"},
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise LoginError(
                    f"'{self.site_name}' 로그인 실패 (HTTP {resp.status}): {body[:200]}"
                )
            data = await resp.json(content_type=None)
            self._token = data.get("key") or data.get("token")

        if not self._token:
            raise LoginError(f"'{self.site_name}' 로그인 응답에 토큰이 없습니다.")
        self.logged_in = True

    async def verify_login(self) -> bool:
        return bool(self._token)

    async def search(self, query: str, max_results: int = 10) -> list:
        if not self._token:
            raise LoginError(f"'{self.site_name}' 로그인이 필요합니다.")

        await self._ensure_session()
        headers = {
            **self._headers,
            "Authorization": f"Token {self._token}",
            "Accept": "application/json",
        }

        url = f"{self.API_SEARCH}?q={quote(query)}"

        async with self.session.get(url, headers=headers) as resp:
            if resp.status == 401:
                raise LoginError(f"'{self.site_name}' 인증 만료. 다시 로그인하세요.")
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        products = []
        for group in data.get("products", []):
            group_name = group.get("name", "")
            manufacturer = group.get("manufacturer", "")
            thumbnail = group.get("thumbnail", "")

            for item in group.get("items", []):
                # 가격: lowest_price가 실제 판매가 (확인됨)
                price = item.get("lowest_price") or 0

                # 상품명 구성: name + standard + unit_count + dosage_form
                name = item.get("name") or group_name
                standard = item.get("standard", "").strip()
                unit_count = item.get("unit_count")
                dosage_form = item.get("dosage_form", "")

                unit_str = f"{unit_count}{dosage_form}" if unit_count and dosage_form else ""
                spec = f"{standard} {unit_str}".strip() if standard else unit_str

                if spec:
                    name = f"{name} {spec}"

                categories = item.get("categories", [])
                cat_str = "/".join(categories) if categories else ""
                wholesalers_count = item.get("wholesalers_count", 0)
                discount_rate = item.get("discount_rate") or item.get("max_discount_rate") or 0

                extra = {}
                if manufacturer:
                    extra["제조사"] = manufacturer
                if cat_str:
                    extra["카테고리"] = cat_str
                if discount_rate:
                    extra["할인율"] = f"{discount_rate}%"
                if wholesalers_count:
                    extra["도매처 수"] = wholesalers_count

                products.append(Product(
                    name=name,
                    price=price,
                    unit_price=unit_str if unit_str else None,
                    url=f"{self.WEB_PRODUCT}{quote(query)}",
                    site_name=self.site_name,
                    image_url=(item.get("images") or [None])[0] or thumbnail,
                    in_stock=item.get("total_qty", 0) > 0,
                    extra_info=extra,
                ))

        products.sort(key=lambda p: p.price if p.price > 0 else 999999999)
        return products[:max_results]


class UPharmMallCrawler(BaseCrawler):
    """
    유팜몰 (upharmmall.co.kr) 전용 크롤러.

    검색 흐름 (확인됨):
      1. 로그인: 메인 페이지에서 __VIEWSTATE 추출 후 폼 POST
      2. 검색:   /Search/Search.aspx?keyword={query} → HTML 파싱
         - tr[data-idx]: 상품 행 (상품코드 포함)
         - span[id*="lblProductName"]: 상품명
         - span[id*="lblPrice"]: 가격 (예: "3,500원")
         - span[id*="lblStandard"]: 규격/제조사 (예: "50매입 / (주)대성메디케어")
    """

    LOGIN_URL  = "https://www.upharmmall.co.kr/"
    SEARCH_URL = "https://www.upharmmall.co.kr/Search/Search.aspx"

    async def login(self):
        username = self.credentials.get("username", "")
        if not username:
            return
        password = get_site_password(self.config)
        if not password:
            raise LoginError(f"'{self.site_name}' 비밀번호 미설정")

        await self._ensure_session()

        # 1) 메인 페이지에서 __VIEWSTATE 추출
        async with self.session.get(self.LOGIN_URL, headers=self._headers) as resp:
            html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")

        viewstate = ""
        vs_el = soup.find("input", {"name": "__VIEWSTATE"})
        if vs_el:
            viewstate = vs_el.get("value", "")

        vsg = ""
        vsg_el = soup.find("input", {"name": "__VIEWSTATEGENERATOR"})
        if vsg_el:
            vsg = vsg_el.get("value", "")

        # 2) ASP.NET 폼 POST 로그인
        login_data = {
            "winClosed": "open",
            "errorMessage": "",
            "informationMessage": "",
            "confirmMessage": "",
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": vsg,
            "ctl00$HeaderControl$txtTopUserID": username,
            "ctl00$HeaderControl$txtTopPwd": password,
            "ctl00$HeaderControl$hidPwd": "",
            "ctl00$HeaderControl$hidSaveidCheck": "1",
            "ctl00$HeaderControl$ibtnTopLogin": "로그인",
            "ctl00$HeaderControl$ex_chk": "on",
            "ctl00$HeaderControl$hidUpPw": "N",
            "ctl00$HeaderControl$hidPwRetn": "",
            "data": "",
            "gubun": "",
            "topMaker": "",
            "topKeyword": "",
            "ctl00$HeaderControl$hiTopWidth": "1920",
            "ctl00$HeaderControl$hiTopHeight": "1080",
        }

        async with self.session.post(
            self.LOGIN_URL, data=login_data, headers={
                **self._headers,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": self.LOGIN_URL,
                "Origin": "https://www.upharmmall.co.kr",
            }
        ) as resp:
            result_html = await resp.text()

        if "mypage" in result_html.lower() or "logout" in result_html.lower() or "로그아웃" in result_html:
            self.logged_in = True
        else:
            raise LoginError(f"'{self.site_name}' 로그인 실패 — ID/비밀번호를 확인하세요.")

    async def verify_login(self) -> bool:
        return self.logged_in

    async def search(self, query: str, max_results: int = 10) -> list:
        await self._ensure_session()

        # 검색 HTML 가져오기
        search_url = f"{self.SEARCH_URL}?keyword={quote(query)}"
        async with self.session.get(search_url, headers={
            **self._headers, "Referer": self.LOGIN_URL,
        }) as resp:
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        products = []

        # 상품 행: <tr data-idx="3H0202730-200"> (확인됨)
        rows = soup.select('tr[data-idx]')

        for row in rows:
            try:
                prod_code = row.get("data-idx", "")

                # 상품명: span[id*="lblProductName"]
                name_el = row.select_one('span[id*="lblProductName"]')
                name = self.clean_text(name_el.get_text()) if name_el else ""
                if not name:
                    continue

                # 가격: span[id*="lblPrice"] → "3,500원"
                price = 0
                price_el = row.select_one('span[id*="lblPrice"]')
                if price_el:
                    price = self.extract_price(price_el.get_text())

                # 규격/제조사: span[id*="lblStandard"] → "50매입 / (주)대성메디케어"
                spec = ""
                maker = ""
                std_el = row.select_one('span[id*="lblStandard"]')
                if std_el:
                    std_text = self.clean_text(std_el.get_text())
                    if " / " in std_text:
                        parts = std_text.split(" / ", 1)
                        spec = parts[0].strip()
                        maker = parts[1].strip()
                    else:
                        spec = std_text

                # 이미지
                img_el = row.select_one('img[src*="ProductImage"]')
                img_url = None
                if img_el:
                    src = img_el.get("src", "")
                    img_url = f"https://www.upharmmall.co.kr{src}" if src.startswith("/") else src

                display_name = f"{name} ({spec})" if spec else name

                extra = {}
                if maker:
                    extra["제조사"] = maker

                products.append(Product(
                    name=display_name,
                    price=price,
                    unit_price=spec if spec else None,
                    url=search_url,
                    site_name=self.site_name,
                    image_url=img_url,
                    in_stock=price > 0,
                    extra_info=extra,
                ))
            except Exception:
                continue

        products.sort(key=lambda p: p.price if p.price > 0 else 999999999)
        return products[:max_results]


class HMPMallCrawler(BaseCrawler):
    """
    한미몰 (hmpmall.co.kr) 전용 크롤러.

    검색 흐름 (확인됨):
      1. 로그인: DWR(Direct Web Remoting) POST
      2. 검색:   /search/searchTwoStepListData.do → JSON
         - productList[].viewProductName: 상품명
         - productList[].minProductUnitPrice: 최저가
         - productList[].manufacturerName: 제조사
         - productList[].packingUnit: 포장단위
         - productList[].stockQuantity: 재고
         - productList[].productMasterImgUrl: 이미지
    """

    BASE       = "https://hmpmall.co.kr"
    LOGIN_URL  = "https://hmpmall.co.kr/dwr/call/plaincall/common/Login.execute.dwr"
    SEARCH_URL = "https://hmpmall.co.kr/search/searchTwoStepListData.do"

    async def login(self):
        username = self.credentials.get("username", "")
        if not username:
            return
        password = get_site_password(self.config)
        if not password:
            raise LoginError(f"'{self.site_name}' 비밀번호 미설정")

        await self._ensure_session()

        # DWR 로그인 요청 생성
        script_session_id = f"{random.randint(100000, 999999)}/{random.randint(100000000, 999999999)}"
        dwr_body = (
            "callCount=1\n"
            "nextReverseAjaxIndex=0\n"
            "c0-scriptName=common/Login\n"
            "c0-methodName=execute\n"
            "c0-id=0\n"
            "c0-e1=string:\n"
            "c0-e2=string:2350001\n"
            f"c0-e3=string:{username}\n"
            f"c0-e4=string:{password}\n"
            "c0-e5=string:on\n"
            "c0-param0=Object_Object:{mallDivCode:reference:c0-e1, "
            "loginPathDivCode:reference:c0-e2, memId:reference:c0-e3, "
            "memPw:reference:c0-e4, cookieID:reference:c0-e5}\n"
            "batchId=0\n"
            "instanceId=0\n"
            "page=/login.do\n"
            f"scriptSessionId={script_session_id}\n"
        )

        async with self.session.post(
            self.LOGIN_URL,
            data=dwr_body.encode("utf-8"),
            headers={
                **self._headers,
                "Content-Type": "text/plain",
                "Referer": f"{self.BASE}/login.do",
            },
        ) as resp:
            # 로그인 성공 시 JSESSIONID 쿠키가 설정됨
            cookies = self.session.cookie_jar.filter_cookies(YarlURL(self.BASE))
            if any("JSESSIONID" in str(c) for c in cookies):
                self.logged_in = True
            elif resp.status == 200:
                # 쿠키 이름이 다를 수 있으므로 200 응답이면 일단 성공 처리
                self.logged_in = True
            else:
                raise LoginError(f"'{self.site_name}' 로그인 실패")

    async def verify_login(self) -> bool:
        return self.logged_in

    async def search(self, query: str, max_results: int = 10) -> list:
        await self._ensure_session()

        # searchTwoStepListData.do JSON API 호출
        params = {
            "productName": query,
            "searchKeyword": query,
            "headerSearchKeyword": query,
            "skip": "1",
            "max": "10000",
            "orderFieldName": "MIN_PROD_PRC",
            "orderType": "ASC",
        }

        async with self.session.get(
            self.SEARCH_URL, params=params,
            headers={
                **self._headers,
                "Referer": f"{self.BASE}/search/searchTwoStepList.do",
                "X-Requested-With": "XMLHttpRequest",
            },
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json(content_type=None)

        product_list = data.get("productList", [])
        products = []

        for item in product_list:
            try:
                name = item.get("viewProductName") or item.get("productName", "")
                if not name:
                    continue

                # 가격: minProductUnitPrice (확인됨)
                price = item.get("minProductUnitPrice") or 0
                if item.get("mrInquiryPriceYn") == "Y":
                    price = 0  # MR문의 상품

                manufacturer = item.get("manufacturerName", "")
                packing_unit = item.get("packingUnit", "")
                stock = item.get("stockQuantity", 0)
                img_path = item.get("productMasterImgUrl", "")
                view_price = int(item.get("viewPrice") or 0)  # 정가 (할인 전)
                new_yn = item.get("newProductYn", "")

                img_url = f"https://www.hmpmall.co.kr{img_path}" if img_path else None

                extra = {}
                if manufacturer:
                    extra["제조사"] = manufacturer
                if view_price > 0 and view_price > price > 0:
                    extra["정가"] = f"₩{view_price:,}"
                if new_yn == "E":
                    stock = 0

                products.append(Product(
                    name=name,
                    price=price,
                    unit_price=packing_unit if packing_unit else None,
                    url=f"{self.BASE}/search/searchTwoStepList.do",
                    site_name=self.site_name,
                    image_url=img_url,
                    in_stock=stock > 0 if stock else False,
                    extra_info=extra,
                ))
            except Exception:
                continue

        products.sort(key=lambda p: p.price if p.price > 0 else 999999999)
        return products[:max_results]


class PlatPharmCrawler(BaseCrawler):
    """
    플랫팜 (platpharm.co.kr) 전용 크롤러.

    검색 흐름 (확인됨):
      1. 로그인: NextAuth.js 기반
         a. GET  /api/auth/csrf → csrfToken 획득
         b. POST /api/auth/callback/credentials → 세션 쿠키 설정
         c. GET  /api/auth/session → {accessToken, refreshToken} 획득
      2. 검색: GET https://api.platpharm.co.kr/v1/customers/search?qs={query}
         - Authorization: Bearer {accessToken}
         - payload.items[].productName: 상품명
         - payload.items[].price: 가격
         - payload.items[].std: 규격 (예: "(개)")
         - payload.items[].vendorName: 도매상
         - payload.items[].stockCount: 재고
    """

    WEB_BASE    = "https://www.platpharm.co.kr"
    API_BASE    = "https://api.platpharm.co.kr"
    CSRF_URL    = "https://www.platpharm.co.kr/api/auth/csrf"
    LOGIN_URL   = "https://www.platpharm.co.kr/api/auth/callback/credentials"
    SESSION_URL = "https://www.platpharm.co.kr/api/auth/session"
    SEARCH_URL  = "https://api.platpharm.co.kr/v1/customers/search"
    IMG_BASE    = "https://api.platpharm.co.kr/images/"

    def __init__(self, site_config: dict):
        super().__init__(site_config)
        self._access_token = None

    async def login(self):
        username = self.credentials.get("username", "")
        if not username:
            return
        password = get_site_password(self.config)
        if not password:
            raise LoginError(f"'{self.site_name}' 비밀번호 미설정")

        await self._ensure_session()

        # 1) CSRF 토큰 획득
        async with self.session.get(self.CSRF_URL, headers=self._headers) as resp:
            csrf_data = await resp.json(content_type=None)
            csrf_token = csrf_data.get("csrfToken", "")

        if not csrf_token:
            raise LoginError(f"'{self.site_name}' CSRF 토큰 획득 실패")

        # 2) 로그인 POST (NextAuth credentials)
        login_data = {
            "email": username,
            "password": password,
            "redirect": "false",
            "callbackUrl": f"{self.WEB_BASE}/",
            "csrfToken": csrf_token,
            "json": "true",
        }

        async with self.session.post(
            self.LOGIN_URL, data=login_data,
            headers={
                **self._headers,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": f"{self.WEB_BASE}/login",
                "Origin": self.WEB_BASE,
            },
        ) as resp:
            if resp.status != 200:
                raise LoginError(f"'{self.site_name}' 로그인 실패 (HTTP {resp.status})")

        # 3) 세션에서 accessToken 획득
        async with self.session.get(
            self.SESSION_URL,
            headers={**self._headers, "Referer": f"{self.WEB_BASE}/"},
        ) as resp:
            session_data = await resp.json(content_type=None)
            self._access_token = session_data.get("accessToken")

        if not self._access_token:
            raise LoginError(f"'{self.site_name}' 세션 토큰 획득 실패. ID/비밀번호를 확인하세요.")
        self.logged_in = True

    async def verify_login(self) -> bool:
        return bool(self._access_token)

    async def search(self, query: str, max_results: int = 10) -> list:
        if not self._access_token:
            raise LoginError(f"'{self.site_name}' 로그인이 필요합니다.")

        await self._ensure_session()

        url = f"{self.SEARCH_URL}?ver=0.0.1&qs={quote(query)}&perPage=10000"

        async with self.session.get(url, headers={
            **self._headers,
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
            "Referer": f"{self.WEB_BASE}/search?qs={quote(query)}",
        }) as resp:
            if resp.status == 401:
                raise LoginError(f"'{self.site_name}' 인증 만료. 다시 로그인하세요.")
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        items = data.get("payload", {}).get("items", [])
        products = []

        for item in items:
            try:
                name = item.get("productName", "")
                if not name:
                    continue

                price = item.get("price") or 0
                std = item.get("std", "")  # "(개)", "(Box)" 등
                vendor = item.get("vendorName", "")
                stock = item.get("stockCount") or 0
                status = item.get("status", "")
                category = item.get("cateName", "")
                thumb = item.get("thumbImg1", "")
                consumer_price = item.get("consumerPrice") or 0

                # 규격을 이름에 포함
                display_name = f"{name} {std}" if std else name

                img_url = f"{self.IMG_BASE}{thumb}" if thumb else None

                extra = {}
                if vendor:
                    extra["제조사"] = vendor
                if category:
                    extra["카테고리"] = category
                if consumer_price and consumer_price > price > 0:
                    extra["소비자가"] = f"₩{consumer_price:,}"

                # 배송 정보
                delivery = item.get("deliveryInfo", {})
                cutoff = delivery.get("cutoffTime", "")
                if cutoff:
                    extra["주문마감"] = f"{cutoff[:2]}:{cutoff[2:]}" if len(cutoff) == 4 else cutoff

                products.append(Product(
                    name=display_name,
                    price=price,
                    unit_price=std if std else None,
                    url=f"{self.WEB_BASE}/search?qs={quote(query)}",
                    site_name=self.site_name,
                    image_url=img_url,
                    in_stock=stock > 0 and status == "PD_SALE",
                    extra_info=extra,
                ))
            except Exception:
                continue

        products.sort(key=lambda p: p.price if p.price > 0 else 999999999)
        return products[:max_results]


class SaeroPharmCrawler(BaseCrawler):
    """
    새로팜 (saeropharm.com) 전용 크롤러.

    검색 흐름 (확인됨):
      1. 로그인: POST /front/ajax/login/loginCheckAjaxEncrypt.do
         - JSON body: {userId, userPw(base64), userAgent, cookieUserIdChk}
         - 비밀번호: b64EncodeUnicode() = Base64 인코딩
      2. 검색: GET /w/product/searchProductList.do?mainSchValue={query}
         - HTML 파싱: div.prd-item[data-no] → 상품 목록
         - p.name: 상품명
         - p.text: 규격 (예: "(1매)", "5매(1EA)")
         - p.amount: 최저가 (예: "230원~")
    """

    BASE       = "https://www.saeropharm.com"
    LOGIN_URL  = "https://www.saeropharm.com/front/ajax/login/loginCheckAjaxEncrypt.do"
    SEARCH_URL = "https://www.saeropharm.com/w/product/searchProductList.do"

    async def login(self):
        username = self.credentials.get("username", "")
        if not username:
            return
        password = get_site_password(self.config)
        if not password:
            raise LoginError(f"'{self.site_name}' 비밀번호 미설정")

        await self._ensure_session()

        # 비밀번호 Base64 인코딩 (b64EncodeUnicode)
        pw_b64 = base64.b64encode(password.encode("utf-8")).decode("utf-8")

        login_data = {
            "userId": username,
            "userPw": pw_b64,
            "userAgent": "",
            "cookieUserIdChk": "N",
        }

        async with self.session.post(
            self.LOGIN_URL,
            json=login_data,
            headers={
                **self._headers,
                "Content-Type": "application/json; charset=utf-8",
                "Referer": f"{self.BASE}/front/login/login.do",
                "Origin": self.BASE,
            },
        ) as resp:
            if resp.status != 200:
                raise LoginError(f"'{self.site_name}' 로그인 실패 (HTTP {resp.status})")
            data = await resp.json(content_type=None)
            flag = str(data.get("flag", ""))
            if flag == "4":
                self.logged_in = True
            elif flag == "0":
                raise LoginError(f"'{self.site_name}' 아이디 또는 비밀번호가 잘못되었습니다.")
            elif flag == "2":
                raise LoginError(f"'{self.site_name}' 회원가입 승인 중입니다.")
            else:
                raise LoginError(f"'{self.site_name}' 로그인 실패 (flag={flag})")

    async def verify_login(self) -> bool:
        return self.logged_in

    async def search(self, query: str, max_results: int = 10) -> list:
        await self._ensure_session()

        search_url = f"{self.SEARCH_URL}?mainSchValue={quote(query)}"
        async with self.session.get(search_url, headers={
            **self._headers, "Referer": f"{self.BASE}/w/main.do",
        }) as resp:
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        products = []

        # 상품: div.prd-item[data-no] (확인됨)
        items = soup.select("div.prd-item[data-no]")

        for item in items:
            try:
                good_sno = item.get("data-no", "")

                # 상품명: p.name
                name_el = item.select_one("p.name")
                name = self.clean_text(name_el.get_text()) if name_el else ""
                if not name:
                    continue

                # 규격: p.text → "(1매)", "5매(1EA)", "대형(5매)" 등
                spec_el = item.select_one("p.text")
                spec = self.clean_text(spec_el.get_text()) if spec_el else ""

                # 가격: p.amount → "230원~", "1,150원~"
                price = 0
                price_el = item.select_one("p.amount")
                if price_el:
                    price_text = price_el.get_text()
                    price = self.extract_price(price_text)

                # 이미지
                img_el = item.select_one(".thumbs img")
                img_url = img_el.get("src", "") if img_el else None

                display_name = f"{name} ({spec})" if spec else name

                products.append(Product(
                    name=display_name,
                    price=price,
                    unit_price=spec if spec else None,
                    url=search_url,
                    site_name=self.site_name,
                    image_url=img_url,
                    in_stock=price > 0,
                    extra_info={},
                ))
            except Exception:
                continue

        products.sort(key=lambda p: p.price if p.price > 0 else 999999999)
        return products[:max_results]


class PharmNutritionCrawler(BaseCrawler):
    """
    팜뉴트리션 (pharmnutrition.co.kr) 전용 크롤러.

    그누보드(PHP) 기반 쇼핑몰.

    검색 흐름 (확인됨):
      1. 로그인: POST /bbs/login_check.php
         - 필드: mb_id, mb_password, url, auto_login=on
         - 성공 시 Location 헤더로 메인 페이지 리다이렉트
      2. 검색 목록: GET /shop/list_all.php?stx={query}
         - HTML에 가격 없음 → <a href="/shop/item.php?it_id=XXXX"> 에서 it_id 추출
      3. 상품 상세: GET /shop/item.php?it_id={it_id} (비동기 병렬)
         - <input id="it_price" value="12500"> → 가격
         - <h2 id="sit_title"> → 상품명
         - <p>포장단위 : ...</p> → 규격
         - data-base-cost 속성 → 배송비
    """

    BASE       = "https://www.pharmnutrition.co.kr"
    LOGIN_URL  = "https://www.pharmnutrition.co.kr/bbs/login_check.php"
    SEARCH_URL = "https://www.pharmnutrition.co.kr/shop/list_all.php"
    ITEM_URL   = "https://www.pharmnutrition.co.kr/shop/item.php"

    async def login(self):
        username = self.credentials.get("username", "")
        if not username:
            return
        password = get_site_password(self.config)
        if not password:
            raise LoginError(f"'{self.site_name}' 비밀번호 미설정")

        await self._ensure_session()

        login_data = {
            "url": self.BASE,
            "mb_id": username,
            "mb_password": password,
            "auto_login": "on",
        }

        async with self.session.post(
            self.LOGIN_URL, data=login_data,
            headers={
                **self._headers,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": f"{self.BASE}/bbs/login.php",
                "Origin": self.BASE,
            },
            allow_redirects=False,
        ) as resp:
            location = resp.headers.get("Location", "")
            if self.BASE in location or "pharmnutrition" in location:
                self.logged_in = True
            else:
                # 리다이렉트 따라가서 로그인 여부 확인
                async with self.session.get(
                    self.BASE, headers=self._headers
                ) as check:
                    html = await check.text()
                    if "로그아웃" in html or "mb_id" not in html:
                        self.logged_in = True
                    else:
                        raise LoginError(f"'{self.site_name}' 로그인 실패. ID/비밀번호를 확인하세요.")

    async def verify_login(self) -> bool:
        return self.logged_in

    async def search(self, query: str, max_results: int = 10) -> list:
        await self._ensure_session()

        # 1) 검색 목록에서 it_id 추출
        search_url = f"{self.SEARCH_URL}?stx={quote(query)}"
        async with self.session.get(search_url, headers={
            **self._headers, "Referer": self.BASE,
        }) as resp:
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")

        # <a href="/shop/item.php?it_id=XXXX"> 패턴 추출
        it_ids = []
        seen = set()
        for a in soup.select('a[href*="item.php?it_id="]'):
            href = a.get("href", "")
            m = re.search(r"it_id=(\d+)", href)
            if m:
                it_id = m.group(1)
                if it_id not in seen:
                    seen.add(it_id)
                    it_ids.append(it_id)

        if not it_ids:
            return []

        # 2) 상품 상세 페이지 병렬 요청 (세마포어 5개 제한)
        sem = asyncio.Semaphore(5)

        async def fetch_item(it_id: str) -> dict | None:
            async with sem:
                try:
                    url = f"{self.ITEM_URL}?it_id={it_id}"
                    async with self.session.get(url, headers={
                        **self._headers, "Referer": search_url,
                    }) as resp:
                        item_html = await resp.text()

                    s = BeautifulSoup(item_html, "html.parser")

                    # 상품명: <h2 id="sit_title">
                    name_el = s.find("h2", {"id": "sit_title"})
                    if not name_el:
                        return None
                    # sound_only span 제거
                    for span in name_el.select(".sound_only"):
                        span.decompose()
                    name = self.clean_text(name_el.get_text())
                    if not name:
                        return None

                    # 가격: <input id="it_price" value="XXXX">
                    price_el = s.find("input", {"id": "it_price"})
                    price = int(price_el["value"]) if price_el and price_el.get("value") else 0

                    # 규격: 포장단위 : ... 텍스트
                    spec = ""
                    for p_el in s.select(".sit_ov_info p, .sit_ov p, article p"):
                        txt = p_el.get_text()
                        if "포장단위" in txt:
                            spec = txt.split(":", 1)[-1].strip()
                            break

                    # 배송비: data-base-cost 속성
                    ship_el = s.find(id="it_send_cost_display")
                    ship_fee = int(ship_el.get("data-base-cost", 0)) if ship_el else 0

                    # 이미지: og:image 메타태그 우선
                    img_url = None
                    og_img = s.find("meta", {"property": "og:image"})
                    if og_img:
                        img_url = og_img.get("content", "")

                    return {
                        "name": name, "price": price, "spec": spec,
                        "ship_fee": ship_fee, "img_url": img_url,
                        "url": url,
                    }
                except Exception:
                    return None

        results = await asyncio.gather(*[fetch_item(i) for i in it_ids[:max_results * 3]])

        products = []
        for r in results:
            if not r or r["price"] <= 0:
                continue
            display_name = f"{r['name']} ({r['spec']})" if r["spec"] else r["name"]
            products.append(Product(
                name=display_name,
                price=r["price"],
                unit_price=r["spec"] if r["spec"] else None,
                url=r["url"],
                site_name=self.site_name,
                image_url=r["img_url"],
                shipping_fee=r["ship_fee"] if r["ship_fee"] > 0 else None,
                in_stock=True,
                extra_info={},
            ))

        products.sort(key=lambda p: p.price if p.price > 0 else 999999999)
        return products[:max_results]


class DesimoneCrawler(BaseCrawler):
    """
    드시모네 약국몰 (hsaless.cafe24.com) 전용 크롤러.

    Cafe24 플랫폼 기반 쇼핑몰.

    검색 흐름 (확인됨):
      1. 로그인:
         a. GET  /member/login.html → sLoginKey 추출 (동적 생성 토큰)
         b. POST /exec/front/Member/login/ → 세션 쿠키 설정
      2. 검색: GET /product/search.html?keyword={query}
         - a.name span → 상품명
         - li[rel="판매가"] span.content span → 가격 (예: "9,900원")
         - li[rel="상품요약정보"] span.content span → 요약/규격
    """

    BASE        = "https://hsaless.cafe24.com"
    LOGIN_PAGE  = "https://hsaless.cafe24.com/member/login.html"
    LOGIN_URL   = "https://hsaless.cafe24.com/exec/front/Member/login/"
    SEARCH_URL  = "https://hsaless.cafe24.com/product/search.html"

    async def login(self):
        username = self.credentials.get("username", "")
        if not username:
            return
        password = get_site_password(self.config)
        if not password:
            raise LoginError(f"'{self.site_name}' 비밀번호 미설정")

        await self._ensure_session()

        # 0) 메인 페이지 방문으로 Cafe24 세션 쿠키 사전 수집
        try:
            await self.session.get(self.BASE, headers=self._headers)
        except Exception:
            pass

        # 1) 로그인 페이지에서 sLoginKey 추출
        async with self.session.get(self.LOGIN_PAGE, headers=self._headers) as resp:
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        login_key = ""

        # hidden input 탐색 (name 또는 id에 sLoginKey 포함)
        for el in soup.find_all("input"):
            n = el.get("name", "") or el.get("id", "")
            if "sLoginKey" in n and el.get("value"):
                login_key = el["value"]
                break

        # JS 변수에서 추출 (Cafe24 패턴)
        if not login_key:
            for script in soup.find_all("script"):
                m = re.search(
                    r'["\'\']sLoginKey["\'\']\s*[,:]\s*["\'\']([a-f0-9]{32})["\'\']'
                    r'|sLoginKey\s*[=:]\s*["\'\']([a-f0-9]{32})["\'\']',
                    script.get_text()
                )
                if m:
                    login_key = m.group(1) or m.group(2)
                    break

        # 2) multipart/form-data 로그인 POST
        import aiohttp as _aiohttp
        form = _aiohttp.FormData()
        form.add_field("returnUrl",           self.BASE + "/")
        form.add_field("forbidIpUrl",         "/index.html")
        form.add_field("certificationUrl",    "/intro/adult_certification.html")
        form.add_field("sIsSnsCheckid",       "sProvider")
        form.add_field("ch_ref",              "checkoutToken")
        form.add_field("member_id",           username)
        form.add_field("member_passwd",       password)
        form.add_field("check_save_id",       "T")
        form.add_field("sLoginKey",           login_key)

        post_headers = {k: v for k, v in self._headers.items() if k.lower() != "content-type"}
        post_headers.update({"Referer": self.LOGIN_PAGE, "Origin": self.BASE})

        async with self.session.post(
            self.LOGIN_URL, data=form,
            headers=post_headers,
            allow_redirects=True,
        ) as resp:
            final_url  = str(resp.url)
            resp_html  = await resp.text()

        # 실패 URL 패턴
        if any(p in final_url for p in ["/member/login", "login_fail"]):
            raise LoginError(f"'{self.site_name}' 로그인 실패. ID/비밀번호를 확인하세요.")

        # 성공 패턴
        ok = any(p in resp_html.lower() for p in ["로그아웃", "logout", "마이페이지", username.lower()])
        if ok or "/member/login" not in final_url:
            self.logged_in = True
        else:
            raise LoginError(
                f"'{self.site_name}' 로그인 실패 (최종 URL: {final_url})"
            )


    async def verify_login(self) -> bool:
        return self.logged_in

    async def search(self, query: str, max_results: int = 10) -> list:
        await self._ensure_session()

        search_url = f"{self.SEARCH_URL}?keyword={quote(query)}"
        async with self.session.get(search_url, headers={
            **self._headers, "Referer": self.BASE,
        }) as resp:
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        products = []

        # Cafe24 검색 결과: .xans-search-listitem 또는 상품 래퍼
        items = soup.select("li.xans-record-, .prd-item, .item, .product-item")
        # 실패 시 description 블록으로 폴백
        if not items:
            items = soup.select("div.description")

        for item in items[:max_results * 3]:
            try:
                # 상품명: a.name 안의 마지막 span
                name_el = item.select_one("a.name")
                if not name_el:
                    continue
                spans = name_el.select("span:not(.title):not(.displaynone)")
                name = self.clean_text(spans[-1].get_text()) if spans else self.clean_text(name_el.get_text())
                if not name:
                    continue

                # 상품 URL
                href = name_el.get("href", "")
                prod_url = f"{self.BASE}{href}" if href.startswith("/") else href

                # 가격: li[rel="판매가"] span.content span
                price = 0
                price_li = item.select_one('li[rel="판매가"]')
                if price_li:
                    price_span = price_li.select_one("span.content span")
                    if price_span:
                        price = self.extract_price(price_span.get_text())

                # 요약/규격: li[rel="상품요약정보"]
                spec = ""
                spec_li = item.select_one('li[rel="상품요약정보"]')
                if spec_li:
                    spec_span = spec_li.select_one("span.content span")
                    if spec_span:
                        spec = self.clean_text(spec_span.get_text())

                # 소비자가 (정가)
                consumer_price = 0
                cons_li = item.select_one('li[rel="소비자가"]')
                if cons_li:
                    cons_span = cons_li.select_one("span.content span")
                    if cons_span:
                        consumer_price = self.extract_price(cons_span.get_text())

                # 이미지
                img_el = item.select_one("img")
                img_url = img_el.get("src", "") if img_el else None
                if img_url and img_url.startswith("//"):
                    img_url = "https:" + img_url

                display_name = f"{name} ({spec})" if spec else name

                extra = {}
                if consumer_price > price > 0:
                    extra["소비자가"] = f"₩{consumer_price:,}"

                products.append(Product(
                    name=display_name,
                    price=price,
                    unit_price=spec if spec else None,
                    url=prod_url or search_url,
                    site_name=self.site_name,
                    image_url=img_url,
                    in_stock=price > 0,
                    extra_info=extra,
                ))
            except Exception:
                continue

        products.sort(key=lambda p: p.price if p.price > 0 else 999999999)
        return products[:max_results]


class PharmStreetCrawler(BaseCrawler):
    """
    팜스트리트 보령 (pharm-street.com) 전용 크롤러.

    JSP 기반 의약품 도매몰.

    검색 흐름 (확인됨):
      1. 로그인: POST /login?site_inflow_path=SIP001 (AJAX/XHR, X-Requested-With 필요)
         - 필드: loginId, password, HANYAK_ACC_DT(고정), sid, encId
         - 응답: JSON {"retCd": "Y"/"N", "retMsg": "..."} (HTML 리다이렉트 아님)
      2. 검색: GET /search/searchPage?query={query}&collection=c_goods&top_totalCount=100
         - dl 요소 파싱
         - dt > em           → 상품명 (highlight span 제거)
         - dd.price > em.price_highlight → 가격 (숫자만)
         - dd > strong       → 제조사
    """

    BASE       = "https://www.pharm-street.com"
    LOGIN_URL  = "https://www.pharm-street.com/login?site_inflow_path=SIP001"
    SEARCH_URL = "https://www.pharm-street.com/search/searchPage"

    async def login(self):
        username = self.credentials.get("username", "")
        if not username:
            return
        password = get_site_password(self.config)
        if not password:
            raise LoginError(f"'{self.site_name}' 비밀번호 미설정")

        await self._ensure_session()

        # 세션 쿠키(JSESSIONID 등) 확보를 위해 메인 페이지를 먼저 방문
        async with self.session.get(f"{self.BASE}/", headers=self._headers) as resp:
            await resp.text()

        login_data = {
            "HANYAK_ACC_DT": "2023-02-21",
            "sid":    "",
            "encId":  "",
            "loginId":  username,
            "password": password,
        }

        # 실제로는 일반 폼 제출이 아니라 AJAX(XHR) 호출이며 JSON으로 응답함
        async with self.session.post(
            self.LOGIN_URL, data=login_data,
            headers={
                **self._headers,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Referer": f"{self.BASE}/",
                "Origin":  self.BASE,
                "X-Requested-With": "XMLHttpRequest",
            },
        ) as resp:
            data = await resp.json(content_type=None)

        if str(data.get("retCd", "")) == "Y":
            self.logged_in = True
        else:
            raise LoginError(f"'{self.site_name}' 로그인 실패: {data.get('retMsg', '알 수 없는 오류')}")

    async def verify_login(self) -> bool:
        return self.logged_in

    async def search(self, query: str, max_results: int = 10) -> list:
        await self._ensure_session()

        params = {
            "query":           query,
            "collection":      "c_goods",
            "top_collection":  "c_goods",
            "top_totalCount":  "200",
            "top_sort":        "ORDERBY1/ASC,RANK/DESC,ORDER_CNT/DESC",
            "recommendKeywordType": "0",
        }
        search_url = f"{self.SEARCH_URL}?{'&'.join(f'{k}={quote(str(v))}' for k, v in params.items())}"

        async with self.session.get(search_url, headers={
            **self._headers, "Referer": self.BASE,
        }) as resp:
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        products = []

        # 상품: <dl> 안에 dt(상품명) + dd.price(가격)
        for dl in soup.select("dl"):
            try:
                # 상품명: dt > em (highlight span 제거)
                dt_el = dl.select_one("dt em")
                if not dt_el:
                    continue
                for span in dt_el.select(".highlight"):
                    span.replace_with(span.get_text())
                name = self.clean_text(dt_el.get_text())
                if not name:
                    continue

                # 가격: dd.price > em.price_highlight
                price = 0
                price_el = dl.select_one("dd.price em.price_highlight")
                if price_el:
                    price = self.extract_price(price_el.get_text())
                if price <= 0:
                    continue

                # 제조사: dd > strong
                maker = ""
                for dd in dl.select("dd strong"):
                    txt = self.clean_text(dd.get_text()).strip("[]").strip()
                    if txt:
                        maker = txt
                        break

                # 이미지
                img_el = dl.select_one("img")
                img_url = None
                if img_el:
                    src = img_el.get("src", "")
                    img_url = f"{self.BASE}{src}" if src.startswith("/") else src

                extra = {}
                if maker:
                    extra["제조사"] = maker

                products.append(Product(
                    name=name,
                    price=price,
                    unit_price=None,
                    url=search_url,
                    site_name=self.site_name,
                    image_url=img_url,
                    in_stock=True,
                    extra_info=extra,
                ))
            except Exception:
                continue

        products.sort(key=lambda p: p.price if p.price > 0 else 999999999)
        return products[:max_results]


class SmartPharmCrawler(BaseCrawler):
    """
    스마트팜 (smartpharm.co.kr) 전용 크롤러.

    Classic ASP 기반 도매 사이트.

    로그인 (확인됨): POST /Login/Login.asp
      - 필드: UserID, UserPW, SaveID(체크박스), AutoLogin(체크박스), reURL(hidden, 빈값)
      - 암호화 없음 — 페이지에 crypto-js/aes.js 등이 없고 onsubmit 핸들러도 없어
        비밀번호를 평문으로 POST함 (HTTPS로만 보호됨)
      - 별도 토큰 없이 세션 쿠키로 인증 유지. 로그아웃은 /Login/Logout.asp

    검색 (확인됨): GET /Goods/Goods_List.asp
      - TopSearchKey: 검색어. ⚠️ 페이지 characterSet이 EUC-KR이라 반드시
        EUC-KR로 인코딩해야 함 (UTF-8로 보내면 검색 결과가 안 나옴)
      - TopSearchGubun=1 (검색 대상: 상품명)
      - TopSearch_CMP_NUM=0002 — 숨김 select에 option이 1개뿐인 고정값
        (검색어와 무관, 항상 그대로 붙이면 됨)
      - ctg / TopSearchsCtg1: 카테고리 코드 (001 전문의약품 … 007 일반상품, 빈값=전체)
      - cmp / TopSearch_MakeCmp: 제조사 코드/명 (자동완성 텍스트박스, 보통 빈값)
      - pdnum: 빈값 (특정 상품코드 직접 조회용으로 추정)
      - 세션 쿠키 필요 (미로그인 시 리스트가 비거나 로그인 페이지로 리다이렉트될
        가능성 있음 — 미로그인 상태는 확인 안 됨)

    상품 목록 결과 (확인됨): 각 상품이 <tr id="GoodsTR"> 행으로 표시되며, 가격까지
    목록에 바로 노출되어 상세 페이지(Goods_View.asp) 조회 없이 파싱 가능.
      - a.list                → 상품명
      - td.smart_nomal (1번째) → 규격 (예: "20ml*5P", "12P", "500ml")
      - td.smart_nomal (2번째) → 제조사 (비어있을 수 있음)
      - td.smart_money2        → 공급가 (예: "2,010원")
      - tr의 onclick 속성 중 iPageGo('GoodsView', '/Goods/Goods_View.asp?Key=XXXX&cmp=')
        에서 Key를 추출해 상세 페이지 URL 구성 (a 태그 href는 javascript:void(0)이라
        직접 사용 불가)
      - img[src] — 이미지 없는 상품은 플레이스홀더(no36.gif)이므로 그 경우는 제외
    """

    BASE       = "https://www.smartpharm.co.kr"
    LOGIN_URL  = "https://www.smartpharm.co.kr/Login/Login.asp"
    SEARCH_URL = "https://www.smartpharm.co.kr/Goods/Goods_List.asp"

    async def login(self):
        username = self.credentials.get("username", "")
        if not username:
            return
        password = get_site_password(self.config)
        if not password:
            raise LoginError(f"'{self.site_name}' 비밀번호 미설정")

        await self._ensure_session()

        login_data = {
            "UserID": username,
            "UserPW": password,
            "SaveID": "on",
            "AutoLogin": "",
            "reURL": "",
        }

        async with self.session.post(
            self.LOGIN_URL, data=login_data,
            headers={
                **self._headers,
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": self.LOGIN_URL,
                "Origin": self.BASE,
            },
        ) as resp:
            html = await resp.text()

        if "Logout.asp" in html or "로그아웃" in html:
            self.logged_in = True
        else:
            async with self.session.get(self.BASE, headers=self._headers) as check:
                check_html = await check.text()
            if "Logout.asp" in check_html or "로그아웃" in check_html:
                self.logged_in = True
            else:
                raise LoginError(f"'{self.site_name}' 로그인 실패. ID/비밀번호를 확인하세요.")

    async def verify_login(self) -> bool:
        return self.logged_in

    async def search(self, query: str, max_results: int = 10) -> list:
        await self._ensure_session()

        # ⚠️ EUC-KR 인코딩 필수 — document.characterSet이 EUC-KR이라
        # UTF-8로 보내면 검색이 되지 않음
        query_euckr = quote(query.encode("euc-kr", errors="ignore"))

        params = {
            "ctg": "", "cmp": "",
            "TopSearchKey": query_euckr,
            "TopSearchGubun": "1",
            "TopSearch_MakeCmp": "",
            "TopSearch_CMP_NUM": "0002",
            "pdnum": "", "TopSearchsCtg1": "",
        }
        search_url = f"{self.SEARCH_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

        async with self.session.get(search_url, headers={
            **self._headers, "Referer": self.BASE,
        }) as resp:
            html = await resp.text(encoding="euc-kr", errors="ignore")

        soup = BeautifulSoup(html, "html.parser")
        products = []

        # 상품 행: <tr id="GoodsTR" ... onclick="...iPageGo('GoodsView', '/Goods/Goods_View.asp?Key=XXXX&cmp=');">
        for row in soup.select('tr[id="GoodsTR"]')[:max_results * 3]:
            try:
                name_el = row.select_one("a.list")
                if not name_el:
                    continue
                name = self.clean_text(name_el.get_text())
                if not name:
                    continue

                # 규격/제조사: td.smart_nomal 2개 (1번째=규격, 2번째=제조사)
                nomal_tds = row.select("td.smart_nomal")
                spec = self.clean_text(nomal_tds[0].get_text()) if len(nomal_tds) > 0 else ""
                maker = self.clean_text(nomal_tds[1].get_text()) if len(nomal_tds) > 1 else ""

                # 공급가: td.smart_money2
                price_el = row.select_one("td.smart_money2")
                price = self.extract_price(price_el.get_text()) if price_el else 0
                if price <= 0:
                    continue

                # 상세 페이지 Key: onclick 속성에서 추출 (href는 javascript:void(0))
                onclick = row.get("onclick", "")
                m = re.search(r"Key=([A-Za-z0-9]+)", onclick)
                prod_url = f"{self.BASE}/Goods/Goods_View.asp?Key={m.group(1)}&cmp=" if m else search_url

                img_el = row.select_one("img")
                img_url = None
                if img_el:
                    src = img_el.get("src", "")
                    if src and "no36.gif" not in src:
                        img_url = f"{self.BASE}{src}" if src.startswith("/") else src

                display_name = f"{name} ({spec})" if spec else name

                extra = {}
                if maker:
                    extra["제조사"] = maker

                products.append(Product(
                    name=display_name,
                    price=price,
                    unit_price=spec if spec else None,
                    url=prod_url,
                    site_name=self.site_name,
                    image_url=img_url,
                    in_stock=True,
                    extra_info=extra,
                ))
            except Exception:
                continue

        products.sort(key=lambda p: p.price if p.price > 0 else 999999999)
        return products[:max_results]


CUSTOM_CRAWLERS = {
    "baropharm":      BaroPharmCrawler,
    "upharmmall":     UPharmMallCrawler,
    "hmpmall":        HMPMallCrawler,
    "platpharm":      PlatPharmCrawler,
    "saeropharm":     SaeroPharmCrawler,
    "pharmnutrition": PharmNutritionCrawler,
    "desimone":       DesimoneCrawler,
    "pharmstreet":    PharmStreetCrawler,
    "smartpharm":     SmartPharmCrawler,
}

BAROPHARM_PRESET = {
    "name": "바로팜",
    "enabled": True,
    "builtin": True,
    "crawler_type": "baropharm",
    "base_url": "https://www.baropharm.com",
    "requires_login": True,
    "credentials": {"username": "", "password_encrypted": ""},
    "login_config": {
        "login_url": "https://api.baropharm.com/api/rest-auth/login/",
        "login_method": "json_api",
        "login_fields": {"username": "{username}", "password": "{password}"},
        "csrf_selector": None, "csrf_field_name": None,
        "login_check_url": None, "login_check_selector": None, "login_check_text": None,
    },
    "selectors": {
        "search_url_pattern": "https://api-v2.baropharm.com/me/search/products?q={query}",
        "product_list": "", "product_name": "", "product_price": "",
        "product_link": "", "product_image": "",
    },
    "extra_config": {},
}

UPHARMMALL_PRESET = {
    "name": "유팜몰",
    "enabled": True,
    "builtin": True,
    "crawler_type": "upharmmall",
    "base_url": "https://www.upharmmall.co.kr",
    "requires_login": True,
    "credentials": {"username": "", "password_encrypted": ""},
    "login_config": {
        "login_url": "https://www.upharmmall.co.kr/",
        "login_method": "form_post",
        "login_fields": {
            "ctl00$HeaderControl$txtTopUserID": "{username}",
            "ctl00$HeaderControl$txtTopPwd": "{password}",
        },
        "csrf_selector": None, "csrf_field_name": None,
        "login_check_url": None, "login_check_selector": None, "login_check_text": None,
    },
    "selectors": {
        "search_url_pattern": "/Search/Search.aspx?keyword={query}",
        "product_list": "", "product_name": "", "product_price": "",
        "product_link": "", "product_image": "",
    },
    "extra_config": {},
}

HMPMALL_PRESET = {
    "name": "한미몰",
    "enabled": True,
    "builtin": True,
    "crawler_type": "hmpmall",
    "base_url": "https://hmpmall.co.kr",
    "requires_login": True,
    "credentials": {"username": "", "password_encrypted": ""},
    "login_config": {
        "login_url": "https://hmpmall.co.kr/dwr/call/plaincall/common/Login.execute.dwr",
        "login_method": "custom",
        "login_fields": {"memId": "{username}", "memPw": "{password}"},
        "csrf_selector": None, "csrf_field_name": None,
        "login_check_url": None, "login_check_selector": None, "login_check_text": None,
    },
    "selectors": {
        "search_url_pattern": "/search/searchTwoStepListData.do?productName={query}&skip=1&max=20",
        "product_list": "", "product_name": "", "product_price": "",
        "product_link": "", "product_image": "",
    },
    "extra_config": {},
}

PLATPHARM_PRESET = {
    "name": "플랫팜",
    "enabled": True,
    "builtin": True,
    "crawler_type": "platpharm",
    "base_url": "https://www.platpharm.co.kr",
    "requires_login": True,
    "credentials": {"username": "", "password_encrypted": ""},
    "login_config": {
        "login_url": "https://www.platpharm.co.kr/api/auth/callback/credentials",
        "login_method": "custom",
        "login_fields": {"email": "{username}", "password": "{password}"},
        "csrf_selector": None, "csrf_field_name": None,
        "login_check_url": None, "login_check_selector": None, "login_check_text": None,
    },
    "selectors": {
        "search_url_pattern": "https://api.platpharm.co.kr/v1/customers/search?qs={query}",
        "product_list": "", "product_name": "", "product_price": "",
        "product_link": "", "product_image": "",
    },
    "extra_config": {},
}

SAEROPHARM_PRESET = {
    "name": "새로팜",
    "enabled": True,
    "builtin": True,
    "crawler_type": "saeropharm",
    "base_url": "https://www.saeropharm.com",
    "requires_login": True,
    "credentials": {"username": "", "password_encrypted": ""},
    "login_config": {
        "login_url": "https://www.saeropharm.com/front/ajax/login/loginCheckAjaxEncrypt.do",
        "login_method": "custom",
        "login_fields": {"userId": "{username}", "userPw": "{password}"},
        "csrf_selector": None, "csrf_field_name": None,
        "login_check_url": None, "login_check_selector": None, "login_check_text": None,
    },
    "selectors": {
        "search_url_pattern": "/w/product/searchProductList.do?mainSchValue={query}",
        "product_list": "", "product_name": "", "product_price": "",
        "product_link": "", "product_image": "",
    },
    "extra_config": {},
}

DESIMONE_PRESET = {
    "name": "드시모네",
    "enabled": True,
    "builtin": True,
    "crawler_type": "desimone",
    "base_url": "https://hsaless.cafe24.com",
    "requires_login": True,
    "credentials": {"username": "", "password_encrypted": ""},
    "login_config": {
        "login_url": "https://hsaless.cafe24.com/exec/front/Member/login/",
        "login_method": "custom",
        "login_fields": {"member_id": "{username}", "member_passwd": "{password}"},
        "csrf_selector": "input[name=sLoginKey]", "csrf_field_name": "sLoginKey",
        "login_check_url": None, "login_check_selector": None, "login_check_text": None,
    },
    "selectors": {
        "search_url_pattern": "/product/search.html?keyword={query}",
        "product_list": "", "product_name": "", "product_price": "",
        "product_link": "", "product_image": "",
    },
    "extra_config": {},
}

PHARMNUTRITION_PRESET = {
    "name": "팜뉴트리션",
    "enabled": True,
    "builtin": True,
    "crawler_type": "pharmnutrition",
    "base_url": "https://www.pharmnutrition.co.kr",
    "requires_login": True,
    "credentials": {"username": "", "password_encrypted": ""},
    "login_config": {
        "login_url": "https://www.pharmnutrition.co.kr/bbs/login_check.php",
        "login_method": "custom",
        "login_fields": {"mb_id": "{username}", "mb_password": "{password}"},
        "csrf_selector": None, "csrf_field_name": None,
        "login_check_url": None, "login_check_selector": None, "login_check_text": None,
    },
    "selectors": {
        "search_url_pattern": "/shop/list_all.php?stx={query}",
        "product_list": "", "product_name": "", "product_price": "",
        "product_link": "", "product_image": "",
    },
    "extra_config": {},
}

# ── 기본 내장 사이트 목록 ──
# 프로그램 최초 실행 시 자동으로 등록됩니다.
# 로그인 정보만 사용자가 직접 설정하면 바로 사용 가능.
PHARMSTREET_PRESET = {
    "name": "팜스트리트",
    "enabled": True,
    "builtin": True,
    "crawler_type": "pharmstreet",
    "base_url": "https://www.pharm-street.com",
    "requires_login": True,
    "credentials": {"username": "", "password_encrypted": ""},
    "login_config": {
        "login_url": "https://www.pharm-street.com/login?site_inflow_path=SIP001",
        "login_method": "custom",
        "login_fields": {"loginId": "{username}", "password": "{password}"},
        "csrf_selector": None, "csrf_field_name": None,
        "login_check_url": None, "login_check_selector": None, "login_check_text": None,
    },
    "selectors": {
        "search_url_pattern": "/search/searchPage?query={query}&collection=c_goods",
        "product_list": "", "product_name": "", "product_price": "",
        "product_link": "", "product_image": "",
    },
    "extra_config": {},
}

# ── 신규 추가 사이트 (v1.4) ──
# 주의: 이 3개 사이트는 아웃바운드 네트워크가 차단된 샌드박스에서 추가되어
# 실제 로그인 요청/응답, 검색 결과 HTML 구조를 직접 확인하지 못했습니다.
# base_url(과 dapmall의 로그인 페이지 URL)만 확정 정보이고, login_url/ID·PW
# 필드명/검색 CSS 셀렉터는 다른 사이트의 일반적인 패턴을 참고한 placeholder입니다.
# 앱의 "사이트 관리 > 수정" 화면에서 실제 로그인 폼/검색 결과 페이지를 보고
# 값을 채우면 GenericCrawler로 정상 동작합니다. (필요 시 전용 크롤러 클래스로 승격 가능)
# 스마트팜은 v1.5에서 로그인/검색 요청 형식이 확인되어 SmartPharmCrawler로
# 승격되었습니다 (아래 별도 섹션 참고).
#
# ── 대웅더샵: v2.2에서 로그인/검색 요청 형식 일부 확인 (실제 페이지 분석 기준).
#   로그인: POST https://www.shop.co.kr/front/front/api/auth/login
#     필드명 userId / userPwd. 암호화 라이브러리(crypto-js 등) 미탑재로
#     평문 전송 추정(HTTPS 의존). payload가 JSON인지 form-urlencoded인지는
#     미확인 — 아래는 form_post(form-urlencoded)로 가정한 값이며 실패 시
#     JSON 방식으로 재시도 필요.
#   검색: GET https://the.shop.co.kr/contents/search?searchKey=all&searchVal={query}
#     searchKey 옵션: all(통합)/상품명/제조사/보험코드/상품코드/포함성분/ATC.
#     별도 JSON API 없이 Next.js SSR 풀 페이지 HTML에 상품 리스트(가격/규격/
#     판매사)가 그대로 렌더링됨을 확인했으나, 정확한 CSS 셀렉터는 미확인이라
#     아래 product_list 등은 여전히 placeholder임 — "사이트 관리 > 수정"에서
#     실제 값 보정 필요.
#   인증 유지: 로그인 도메인(www.shop.co.kr)과 서비스 도메인(the.shop.co.kr)이
#     달라 `.shop.co.kr` 상위 도메인 쿠키로 세션을 공유하는 SSO 구조로 추정.
DAEWOONG_THESHOP_PRESET = {
    "name": "대웅더샵",
    "enabled": True,
    "builtin": True,
    "crawler_type": "generic",
    "base_url": "https://the.shop.co.kr",
    "requires_login": True,
    "credentials": {"username": "", "password_encrypted": ""},
    "login_config": {
        "login_url": "https://www.shop.co.kr/front/front/api/auth/login", "login_method": "form_post",
        "login_fields": {"userId": "{username}", "userPwd": "{password}"},
        "csrf_selector": None, "csrf_field_name": None,
        "login_check_url": None, "login_check_selector": None, "login_check_text": None,
    },
    "selectors": {
        "search_url_pattern": "/contents/search?searchKey=all&searchVal={query}",
        "product_list": ".product-item", "product_name": ".product-name",
        "product_price": ".product-price", "product_link": "a[href]", "product_image": "img",
    },
    "extra_config": {},
}

DAPMALL_PRESET = {
    "name": "동아DAPmall",
    "enabled": True,
    "builtin": True,
    "crawler_type": "generic",
    "base_url": "https://www.dapmall.com",
    "requires_login": True,
    "credentials": {"username": "", "password_encrypted": ""},
    "login_config": {
        "login_url": "https://www.dapmall.com/auth/login", "login_method": "form_post",
        "login_fields": {"user_id": "{username}", "password": "{password}"},
        "csrf_selector": None, "csrf_field_name": None,
        "login_check_url": None, "login_check_selector": None, "login_check_text": None,
    },
    "selectors": {
        "search_url_pattern": "/search?keyword={query}",
        "product_list": ".product-item", "product_name": ".product-name",
        "product_price": ".product-price", "product_link": "a[href]", "product_image": "img",
    },
    "extra_config": {},
}

CUPHARM_PRESET = {
    "name": "서울약사신협",
    "enabled": True,
    "builtin": True,
    "crawler_type": "generic",
    "base_url": "https://www.cupharm.kr",
    "requires_login": True,
    "credentials": {"username": "", "password_encrypted": ""},
    "login_config": {
        # main.asp 확장자로 보아 Classic ASP 기반으로 추정 (미검증)
        "login_url": "/member/login.asp", "login_method": "form_post",
        "login_fields": {"user_id": "{username}", "password": "{password}"},
        "csrf_selector": None, "csrf_field_name": None,
        "login_check_url": None, "login_check_selector": None, "login_check_text": None,
    },
    "selectors": {
        "search_url_pattern": "/shop/search.asp?keyword={query}",
        "product_list": ".product-item", "product_name": ".product-name",
        "product_price": ".product-price", "product_link": "a[href]", "product_image": "img",
    },
    "extra_config": {},
}

# ── 스마트팜: v1.5에서 로그인/검색 요청 형식 확인, v1.6에서 상품 목록 결과
# HTML 구조까지 확인됨 (SmartPharmCrawler로 승격). 상세는 SmartPharmCrawler
# 클래스 docstring 및 search() 참고.
SMARTPHARM_PRESET = {
    "name": "스마트팜",
    "enabled": True,
    "builtin": True,
    "crawler_type": "smartpharm",
    "base_url": "https://www.smartpharm.co.kr",
    "requires_login": True,
    "credentials": {"username": "", "password_encrypted": ""},
    "login_config": {
        "login_url": "https://www.smartpharm.co.kr/Login/Login.asp",
        "login_method": "custom",
        "login_fields": {"UserID": "{username}", "UserPW": "{password}"},
        "csrf_selector": None, "csrf_field_name": None,
        "login_check_url": None, "login_check_selector": None, "login_check_text": None,
    },
    "selectors": {
        "search_url_pattern": "/Goods/Goods_List.asp?ctg=&cmp=&TopSearchKey={query}&TopSearchGubun=1&TopSearch_MakeCmp=&TopSearch_CMP_NUM=0002&pdnum=&TopSearchsCtg1=",
        "product_list": "", "product_name": "", "product_price": "",
        "product_link": "", "product_image": "",
    },
    "extra_config": {},
}

BUILTIN_SITES = [
    BAROPHARM_PRESET,
    UPHARMMALL_PRESET,
    HMPMALL_PRESET,
    PLATPHARM_PRESET,
    SAEROPHARM_PRESET,
    PHARMNUTRITION_PRESET,
    DESIMONE_PRESET,
    PHARMSTREET_PRESET,
    DAEWOONG_THESHOP_PRESET,
    DAPMALL_PRESET,
    CUPHARM_PRESET,
    SMARTPHARM_PRESET,
]

def create_crawler(sc):
    ct = sc.get("crawler_type", "generic")
    if ct == "demo": return DemoCrawler(sc)
    if ct in CUSTOM_CRAWLERS: return CUSTOM_CRAWLERS[ct](sc)
    return GenericCrawler(sc)


async def search_site(sc, query, max_results):
    start = time.time(); crawler = None
    try:
        crawler = create_crawler(sc)
        if sc.get("requires_login") or sc.get("credentials", {}).get("username"):
            await crawler.login()
        products = await crawler.search(query, max_results)
        return SearchResult(sc["name"], query, products, elapsed_sec=round(time.time()-start, 2))
    except Exception as e:
        return SearchResult(sc["name"], query, [], error=str(e), elapsed_sec=round(time.time()-start, 2))
    finally:
        if crawler: await crawler.close()

async def search_all(query, config):
    sites = [s for s in config.get("sites", []) if s.get("enabled", True)]
    if not sites: return []
    mx = config.get("settings", {}).get("max_results_per_site", 10)
    return list(await asyncio.gather(*[search_site(s, query, mx) for s in sites]))


# ═══════════════════════════════════════════════════════════════
# 5. GUI 애플리케이션
# ═══════════════════════════════════════════════════════════════

class App(tk.Tk):
    """메인 윈도우"""

    # ── 색상 테마 ──
    BG       = "#1a1a2e"
    BG2      = "#16213e"
    BG3      = "#0f3460"
    ACCENT   = "#e94560"
    ACCENT2  = "#533483"
    TEXT     = "#eaeaea"
    TEXT2    = "#a0a0b8"
    GREEN    = "#00d2a0"
    YELLOW   = "#ffc107"
    CARD_BG  = "#1e2a45"
    ENTRY_BG = "#253555"

    def __init__(self):
        super().__init__()
        self.title(f"도매 최저가 비교 v{__version__}")
        self.geometry("960x700")
        self.minsize(800, 600)
        self.configure(bg=self.BG)
        self.config_data = load_config()
        self._all_products = []
        self._sort_col = None
        self._sort_asc = True
        self._ctx_last_cell = ""
        self._ctx_last_row  = None

        # 스타일
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=self.BG, foreground=self.TEXT, font=("맑은 고딕", 10))
        style.configure("TNotebook", background=self.BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=self.BG2, foreground=self.TEXT2,
                         padding=[18, 8], font=("맑은 고딕", 10, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", self.BG3)],
                  foreground=[("selected", self.TEXT)])
        style.configure("TFrame", background=self.BG)
        style.configure("Card.TFrame", background=self.CARD_BG)
        style.configure("TLabel", background=self.BG, foreground=self.TEXT)
        style.configure("Card.TLabel", background=self.CARD_BG, foreground=self.TEXT)
        style.configure("Sub.TLabel", background=self.BG, foreground=self.TEXT2, font=("맑은 고딕", 9))
        style.configure("Title.TLabel", font=("맑은 고딕", 13, "bold"), foreground=self.TEXT, background=self.BG)
        style.configure("Big.TLabel", font=("맑은 고딕", 22, "bold"), foreground=self.ACCENT, background=self.BG)
        style.configure("Accent.TButton", background=self.ACCENT, foreground="white", font=("맑은 고딕", 10, "bold"), padding=[16, 8])
        style.map("Accent.TButton", background=[("active", "#c73a52")])
        style.configure("Green.TButton", background=self.GREEN, foreground="#111", font=("맑은 고딕", 10, "bold"), padding=[12, 6])
        style.map("Green.TButton", background=[("active", "#00b88a")])
        style.configure("Flat.TButton", background=self.BG3, foreground=self.TEXT, padding=[10, 6])
        style.map("Flat.TButton", background=[("active", self.ACCENT2)])
        style.configure("Danger.TButton", background="#c0392b", foreground="white", padding=[10, 6])
        style.map("Danger.TButton", background=[("active", "#e74c3c")])
        style.configure("Treeview", background=self.CARD_BG, foreground=self.TEXT, fieldbackground=self.CARD_BG,
                         rowheight=32, font=("맑은 고딕", 10))
        style.configure("Treeview.Heading", background=self.BG3, foreground=self.TEXT, font=("맑은 고딕", 10, "bold"))
        style.map("Treeview", background=[("selected", self.BG3)])

        self._build_ui()

    # ────────────────────────────────
    # UI 구성
    # ────────────────────────────────
    def _build_ui(self):
        # 상단 헤더
        header = tk.Frame(self, bg=self.BG, height=60)
        header.pack(fill="x", padx=20, pady=(15, 5))
        header.pack_propagate(False)
        tk.Label(header, text="🏪 도매 최저가 비교", font=("맑은 고딕", 18, "bold"),
                 bg=self.BG, fg=self.TEXT).pack(side="left")
        tk.Label(header, text=f"v{__version__}  |  암호화: {cred_mgr.method}",
                 font=("맑은 고딕", 9), bg=self.BG, fg=self.TEXT2).pack(side="right")

        # 탭
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=5)

        self._build_search_tab()
        self._build_favorites_tab()
        self._build_sites_tab()
        self._build_memo_tab()
        self._build_settings_tab()

    # ──────── 검색 탭 ────────
    def _build_search_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  🔍 검색  ")

        # 검색 바
        bar = tk.Frame(tab, bg=self.BG)
        bar.pack(fill="x", padx=20, pady=(20, 10))

        tk.Label(bar, text="검색어", font=("맑은 고딕", 10, "bold"), bg=self.BG, fg=self.TEXT).pack(side="left", padx=(0, 8))
        self.search_var = tk.StringVar()
        entry = tk.Entry(bar, textvariable=self.search_var, font=("맑은 고딕", 13),
                         bg=self.ENTRY_BG, fg=self.TEXT, insertbackground=self.TEXT,
                         relief="flat", width=30)
        entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 10))
        entry.bind("<Return>", lambda e: self._do_search())

        self.sort_var = tk.StringVar(value="price")
        sort_frame = tk.Frame(bar, bg=self.BG)
        sort_frame.pack(side="left", padx=(0, 10))
        tk.Label(sort_frame, text="정렬", font=("맑은 고딕", 9), bg=self.BG, fg=self.TEXT2).pack(side="left")
        for txt, val in [("가격", "price"), ("이름", "name")]:
            tk.Radiobutton(sort_frame, text=txt, variable=self.sort_var, value=val,
                           bg=self.BG, fg=self.TEXT, selectcolor=self.BG3, activebackground=self.BG,
                           activeforeground=self.TEXT, font=("맑은 고딕", 9)).pack(side="left")

        ttk.Button(bar, text="🔍 검색", style="Accent.TButton", command=self._do_search).pack(side="left")

        # 상태 바
        self.status_var = tk.StringVar(value="검색어를 입력하고 Enter 또는 검색 버튼을 누르세요")
        tk.Label(tab, textvariable=self.status_var, bg=self.BG, fg=self.TEXT2,
                 font=("맑은 고딕", 9), anchor="w").pack(fill="x", padx=20)

        # 사이트별 결과 건수 — 0건/오류인 사이트를 검색할 때마다 바로 확인 가능
        self.site_status_var = tk.StringVar(value="")
        tk.Label(tab, textvariable=self.site_status_var, bg=self.BG, fg=self.TEXT2,
                 font=("맑은 고딕", 8), anchor="w", justify="left",
                 wraplength=900).pack(fill="x", padx=20, pady=(2, 0))

        # 결과 요약 카드
        self.summary_frame = tk.Frame(tab, bg=self.BG)
        self.summary_frame.pack(fill="x", padx=20, pady=(5, 5))

        # 결과 테이블
        tree_frame = tk.Frame(tab, bg=self.BG)
        tree_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        cols = ("rank", "site", "name", "price", "unit_price", "maker", "stock")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self._col_headings = {
            "rank": ("#", 40), "site": ("사이트", 100), "name": ("상품명", 320),
            "price": ("가격", 100),
            "unit_price": ("단가/규격", 110), "maker": ("제조사", 130), "stock": ("재고", 55),
        }
        for col, (txt, w) in self._col_headings.items():
            self.tree.heading(col, text=txt, command=lambda c=col: self._sort_tree(c))
            anchor = "center" if col in ("rank", "stock") else "e" if col == "price" else "w"
            self.tree.column(col, width=w, anchor=anchor, minwidth=40)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Button-3>", self._on_tree_right_click)

        # 우클릭 컨텍스트 메뉴
        self._ctx_menu = tk.Menu(self, tearoff=0, bg=self.CARD_BG, fg=self.TEXT,
                                  activebackground=self.BG3, activeforeground=self.TEXT,
                                  font=("맑은 고딕", 10))
        self._ctx_menu.add_command(label="📋 셀 내용 복사", command=self._copy_cell)
        self._ctx_menu.add_command(label="⭐ 즐겨찾기 추가", command=self._add_to_favorites)
        self._ctx_menu.add_command(label="🔍 이 상품 사이트에서 검색", command=self._open_product_search)

    # ──────── 즐겨찾기 탭 ────────
    def _build_favorites_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  ⭐ 즐겨찾기  ")

        # 도구 버튼
        toolbar = tk.Frame(tab, bg=self.BG)
        toolbar.pack(fill="x", padx=20, pady=(15, 10))
        tk.Label(toolbar, text="검색 결과에서 우클릭 → 즐겨찾기 추가로 등록하세요",
                 bg=self.BG, fg=self.TEXT2, font=("맑은 고딕", 9)).pack(side="left")
        ttk.Button(toolbar, text="🗑️ 삭제", style="Danger.TButton",
                   command=self._delete_favorite).pack(side="right")

        # 즐겨찾기 목록
        fav_frame = tk.Frame(tab, bg=self.BG)
        fav_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        fav_cols = ("site", "name", "price", "unit_price", "maker", "added_at")
        self.fav_tree = ttk.Treeview(fav_frame, columns=fav_cols, show="headings",
                                      selectmode="browse")
        for col, txt, w in [
            ("site", "사이트", 90), ("name", "상품명", 320), ("price", "가격", 90),
            ("unit_price", "단가/규격", 100), ("maker", "제조사", 130), ("added_at", "추가일시", 130),
        ]:
            self.fav_tree.heading(col, text=txt)
            self.fav_tree.column(col, width=w, minwidth=40,
                                  anchor="e" if col == "price" else "w")

        fav_sb = ttk.Scrollbar(fav_frame, orient="vertical", command=self.fav_tree.yview)
        self.fav_tree.configure(yscrollcommand=fav_sb.set)
        self.fav_tree.pack(side="left", fill="both", expand=True)
        fav_sb.pack(side="right", fill="y")
        self.fav_tree.bind("<Double-1>", self._on_fav_double_click)
        self._refresh_favorites()

    def _refresh_favorites(self):
        if not hasattr(self, "fav_tree"):
            return
        self.fav_tree.delete(*self.fav_tree.get_children())
        for i, f in enumerate(self.config_data.get("favorites", [])):
            price_txt = f"₩{f['price']:,}" if f.get("price", 0) > 0 else "-"
            self.fav_tree.insert("", "end", iid=f"f_{i}", values=(
                f.get("site_name", ""), f.get("name", ""),
                price_txt, f.get("unit_price") or "-",
                f.get("maker", ""), f.get("added_at", ""),
            ))

    def _delete_favorite(self):
        sel = self.fav_tree.selection()
        if not sel:
            messagebox.showinfo("알림", "삭제할 항목을 선택하세요")
            return
        iid = sel[0]
        if not iid.startswith("f_"):
            return
        idx = int(iid[2:])
        favs = self.config_data.get("favorites", [])
        if 0 <= idx < len(favs):
            name = favs[idx].get("name", "")[:30]
            if messagebox.askyesno("삭제 확인", f"'{name}'\n즐겨찾기에서 삭제할까요?"):
                favs.pop(idx)
                save_config(self.config_data)
                self._refresh_favorites()

    def _on_fav_double_click(self, event):
        """즐겨찾기 더블클릭 → 해당 사이트에서 상품명 검색"""
        sel = self.fav_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("f_"):
            idx = int(iid[2:])
            favs = self.config_data.get("favorites", [])
            if 0 <= idx < len(favs):
                f = favs[idx]
                pattern = SITE_SEARCH_PATTERNS.get(f.get("site_name", ""), "")
                url = pattern.replace("{query}", quote(f.get("name", ""))) if pattern else f.get("url", "")
                if url.startswith("http"):
                    webbrowser.open(url)

    # ──────── 사이트 관리 탭 ────────
    def _build_sites_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  📋 사이트 관리  ")

        # 도구 버튼
        toolbar = tk.Frame(tab, bg=self.BG)
        toolbar.pack(fill="x", padx=20, pady=(15, 10))
        ttk.Button(toolbar, text="➕ 사이트 추가", style="Green.TButton", command=self._add_site).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="✏️ 수정", style="Flat.TButton", command=self._edit_site).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="🔑 로그인 설정", style="Flat.TButton", command=self._edit_credentials).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="🔌 로그인 테스트", style="Flat.TButton", command=self._test_login).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="🗑️ 삭제", style="Danger.TButton", command=self._delete_site).pack(side="right")
        ttk.Button(toolbar, text="📥 데모 불러오기", style="Flat.TButton", command=self._load_demo).pack(side="right", padx=(0, 8))

        # 사이트 목록
        list_frame = tk.Frame(tab, bg=self.BG)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        cols = ("name", "url", "crawler", "login", "status")
        self.site_tree = ttk.Treeview(list_frame, columns=cols, show="headings", selectmode="browse")
        for col, txt, w in [("name", "사이트 이름", 150), ("url", "URL", 250), ("crawler", "크롤러", 80),
                            ("login", "로그인", 160), ("status", "상태", 80)]:
            self.site_tree.heading(col, text=txt)
            self.site_tree.column(col, width=w, minwidth=50)

        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.site_tree.yview)
        self.site_tree.configure(yscrollcommand=sb.set)
        self.site_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.site_tree.bind("<Double-1>", lambda e: self._edit_site())

        self._refresh_site_list()

    # ──────── 메모장 탭 ────────
    def _build_memo_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  📝 메모장  ")

        # 상단 안내 + 저장 버튼
        header = tk.Frame(tab, bg=self.BG)
        header.pack(fill="x", padx=20, pady=(15, 5))

        tk.Label(header, text="사이트별 로그인 정보 등을 기록하세요",
                 bg=self.BG, fg=self.TEXT2, font=("맑은 고딕", 9)).pack(side="left")
        tk.Label(header, text="🔒 암호화 저장", bg=self.BG, fg=self.GREEN,
                 font=("맑은 고딕", 9, "bold")).pack(side="left", padx=(8, 0))

        ttk.Button(header, text="💾 저장", style="Green.TButton",
                   command=self._save_memo).pack(side="right")

        # 텍스트 영역
        text_frame = tk.Frame(tab, bg=self.BG)
        text_frame.pack(fill="both", expand=True, padx=20, pady=(5, 15))

        self.memo_text = tk.Text(
            text_frame, font=("맑은 고딕", 11), bg=self.ENTRY_BG, fg=self.TEXT,
            insertbackground=self.TEXT, relief="flat", wrap="word",
            padx=15, pady=12, spacing1=4, spacing3=4,
        )
        memo_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.memo_text.yview)
        self.memo_text.configure(yscrollcommand=memo_scroll.set)
        self.memo_text.pack(side="left", fill="both", expand=True)
        memo_scroll.pack(side="right", fill="y")

        # 기존 메모 불러오기
        saved = self._load_memo()
        if saved:
            self.memo_text.insert("1.0", saved)
        else:
            # 기본 템플릿
            template = (
                "═══ 사이트별 로그인 정보 ═══\n\n"
                "▶ 바로팜\n"
                "  아이디: \n"
                "  비밀번호: \n\n"
                "▶ 유팜몰\n"
                "  아이디: \n"
                "  비밀번호: \n\n"
                "▶ 한미몰\n"
                "  아이디: \n"
                "  비밀번호: \n\n"
                "▶ 플랫팜\n"
                "  아이디: \n"
                "  비밀번호: \n\n"
                "▶ 새로팜\n"
                "  아이디: \n"
                "  비밀번호: \n\n"
                "═══ 기타 메모 ═══\n\n"
            )
            self.memo_text.insert("1.0", template)

    def _save_memo(self):
        """메모 내용을 암호화하여 파일에 저장"""
        content = self.memo_text.get("1.0", "end-1c")
        try:
            encrypted = cred_mgr.encrypt(content)
            MEMO_PATH.write_text(encrypted, encoding="utf-8")
            messagebox.showinfo("저장 완료", f"메모가 암호화되어 저장되었습니다.\n({cred_mgr.method})")
        except Exception as e:
            messagebox.showerror("저장 실패", f"메모 저장 중 오류: {e}")

    def _load_memo(self) -> str:
        """암호화된 메모 파일을 읽어서 복호화"""
        if not MEMO_PATH.exists():
            return ""
        try:
            encrypted = MEMO_PATH.read_text(encoding="utf-8")
            return cred_mgr.decrypt(encrypted)
        except Exception:
            return ""

    # ──────── 설정 탭 ────────
    def _build_settings_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  ⚙️ 설정  ")

        container = tk.Frame(tab, bg=self.BG)
        container.pack(padx=40, pady=30, anchor="nw")

        settings = self.config_data.get("settings", {})

        row = 0
        tk.Label(container, text="사이트당 최대 결과 수", bg=self.BG, fg=self.TEXT, font=("맑은 고딕", 10)).grid(row=row, column=0, sticky="w", pady=8)
        self.max_results_var = tk.StringVar(value=str(settings.get("max_results_per_site", 10)))
        tk.Entry(container, textvariable=self.max_results_var, width=8, bg=self.ENTRY_BG, fg=self.TEXT,
                 insertbackground=self.TEXT, relief="flat", font=("맑은 고딕", 11)).grid(row=row, column=1, sticky="w", padx=15)

        row += 1
        tk.Label(container, text="타임아웃 (초)", bg=self.BG, fg=self.TEXT, font=("맑은 고딕", 10)).grid(row=row, column=0, sticky="w", pady=8)
        self.timeout_var = tk.StringVar(value=str(settings.get("timeout_seconds", 30)))
        tk.Entry(container, textvariable=self.timeout_var, width=8, bg=self.ENTRY_BG, fg=self.TEXT,
                 insertbackground=self.TEXT, relief="flat", font=("맑은 고딕", 11)).grid(row=row, column=1, sticky="w", padx=15)

        row += 1
        tk.Label(container, text="", bg=self.BG).grid(row=row, column=0, pady=5)

        row += 1
        ttk.Button(container, text="💾 설정 저장", style="Green.TButton", command=self._save_settings).grid(row=row, column=0, sticky="w", pady=10)

        row += 2
        tk.Label(container, text="프로그램 정보", bg=self.BG, fg=self.TEXT, font=("맑은 고딕", 11, "bold")).grid(row=row, column=0, sticky="w", pady=(20, 5))
        row += 1
        info = f"버전: v{__version__}\n암호화: {cred_mgr.method}\n설정 파일: {CONFIG_PATH}"
        tk.Label(container, text=info, bg=self.BG, fg=self.TEXT2, font=("맑은 고딕", 9), justify="left").grid(row=row, column=0, columnspan=2, sticky="w")

    # ────────────────────────────────
    # 검색 로직
    # ────────────────────────────────
    def _do_search(self):
        query = self.search_var.get().strip()
        if not query:
            messagebox.showwarning("알림", "검색어를 입력하세요")
            return

        sites = [s for s in self.config_data.get("sites", []) if s.get("enabled", True)]
        if not sites:
            messagebox.showinfo("알림", "활성 사이트가 없습니다.\n'사이트 관리' 탭에서 사이트를 추가하세요.")
            return

        self.status_var.set(f"🔍 '{query}' 검색 중... ({len(sites)}개 사이트)")
        self.site_status_var.set("")
        self.tree.delete(*self.tree.get_children())
        for w in self.summary_frame.winfo_children():
            w.destroy()
        self.update_idletasks()

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(search_all(query, self.config_data))
            finally:
                loop.close()
            self.after(0, lambda: self._show_results(results, query))

        threading.Thread(target=run, daemon=True).start()

    def _show_results(self, results, query):
        self._all_products = []
        errors = []
        site_summary = []
        for r in results:
            if r.error:
                errors.append(f"{r.site_name}: {r.error}")
                site_summary.append(f"{r.site_name}:오류⚠")
            elif not r.products:
                site_summary.append(f"{r.site_name}:0건⚠")
            else:
                self._all_products.extend(r.products)
                site_summary.append(f"{r.site_name}:{len(r.products)}건")
        self.site_status_var.set("사이트별 결과  " + "  ·  ".join(site_summary))

        # 정렬
        sort_key = self.sort_var.get()
        if sort_key == "name":
            self._all_products.sort(key=lambda p: p.name)
        else:
            self._all_products.sort(key=lambda p: p.price if p.price > 0 else 999999999)

        # 요약 카드
        for w in self.summary_frame.winfo_children():
            w.destroy()

        priced = [p for p in self._all_products if p.price > 0]
        if self._all_products:
            if priced:
                lowest = min(priced, key=lambda p: p.price)
                low_price = f"₩{lowest.price:,}"
                low_site = lowest.site_name
                low_name = lowest.name[:20]
            else:
                low_price = "-"
                low_site = "-"
                low_name = "-"
            cards_data = [
                ("총 검색 결과", f"{len(self._all_products)}개", self.TEXT),
                ("최저가", low_price, self.GREEN),
                ("최저가 사이트", low_site, self.YELLOW),
                ("최저가 상품", low_name, self.TEXT),
            ]
            for title, value, color in cards_data:
                card = tk.Frame(self.summary_frame, bg=self.CARD_BG, padx=15, pady=8)
                card.pack(side="left", padx=(0, 10), fill="x", expand=True)
                tk.Label(card, text=title, bg=self.CARD_BG, fg=self.TEXT2, font=("맑은 고딕", 9)).pack(anchor="w")
                tk.Label(card, text=value, bg=self.CARD_BG, fg=color, font=("맑은 고딕", 13, "bold")).pack(anchor="w")

        # 테이블 채우기
        self.tree.delete(*self.tree.get_children())
        self._sort_col = None
        # 헤딩 화살표 초기화
        for c, (base_txt, _) in self._col_headings.items():
            self.tree.heading(c, text=base_txt)

        for i, p in enumerate(self._all_products, 1):
            stock_txt = "✓" if p.in_stock else "품절"
            price_txt = f"₩{p.price:,}" if p.price > 0 else "가격문의"
            maker = p.extra_info.get("제조사", "")

            self.tree.insert("", "end", iid=f"p_{i-1}", values=(
                i, p.site_name, p.name,
                price_txt,
                p.unit_price or "-", maker, stock_txt
            ))

        # 상태 바
        err_txt = f"  |  ⚠ 오류: {', '.join(errors)}" if errors else ""
        self.status_var.set(f"✓ '{query}' 검색 완료 — {len(self._all_products)}개 결과{err_txt}")

    def _sort_tree(self, col):
        """컬럼 클릭 → 오름차순/내림차순 토글 정렬"""
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True

        num_cols = ("rank", "price")
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]

        if col in num_cols:
            def num_key(t):
                digits = re.sub(r"[^\d]", "", t[0])
                v = int(digits) if digits else (999999999 if self._sort_asc else -1)
                return v
            items.sort(key=num_key, reverse=not self._sort_asc)
        else:
            items.sort(key=lambda t: t[0].lower(), reverse=not self._sort_asc)

        for idx, (_, k) in enumerate(items):
            self.tree.move(k, "", idx)

        # 헤딩에 ▲/▼ 표시
        arrow = " ▲" if self._sort_asc else " ▼"
        for c, (base_txt, _) in self._col_headings.items():
            display = base_txt + arrow if c == col else base_txt
            self.tree.heading(c, text=display)

    def _on_tree_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("p_"):
            idx = int(iid[2:])
            if 0 <= idx < len(self._all_products):
                self._open_product_search_by_idx(idx)

    def _open_product_search_by_idx(self, idx: int):
        """상품명으로 해당 사이트 검색 결과 페이지 열기"""
        p = self._all_products[idx]
        pattern = SITE_SEARCH_PATTERNS.get(p.site_name, "")
        if pattern:
            url = pattern.replace("{query}", quote(p.name))
        else:
            url = p.url
        if url.startswith("http"):
            webbrowser.open(url)

    def _get_selected_product_idx(self) -> int:
        """현재 선택된 트리 행의 _all_products 인덱스 반환"""
        sel = self.tree.selection()
        if not sel:
            return -1
        iid = sel[0]
        if iid.startswith("p_"):
            return int(iid[2:])
        return -1

    def _on_tree_right_click(self, event):
        """우클릭 컨텍스트 메뉴"""
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id or not col_id:
            return
        self.tree.selection_set(row_id)

        # 클릭된 셀 값 추출
        cols = ("rank", "site", "name", "price", "unit_price", "maker", "stock")
        try:
            col_idx = int(col_id.replace("#", "")) - 1
        except ValueError:
            col_idx = -1
        cell_val = self.tree.set(row_id, cols[col_idx]) if 0 <= col_idx < len(cols) else ""
        self._ctx_last_cell = cell_val
        self._ctx_last_row  = row_id

        # 메뉴 레이블 업데이트
        preview = cell_val[:28] + "…" if len(cell_val) > 28 else cell_val
        self._ctx_menu.entryconfig(0, label=f"📋  복사:  {preview}")
        self._ctx_menu.post(event.x_root, event.y_root)

    def _copy_cell(self):
        """클립보드에 셀 값 복사"""
        val = getattr(self, "_ctx_last_cell", "")
        self.clipboard_clear()
        self.clipboard_append(val)

    def _open_product_search(self):
        """우클릭 메뉴에서 사이트 검색 열기"""
        idx = self._get_selected_product_idx()
        if idx >= 0:
            self._open_product_search_by_idx(idx)

    def _add_to_favorites(self):
        """선택된 상품을 즐겨찾기에 추가"""
        idx = self._get_selected_product_idx()
        if idx < 0:
            return
        p = self._all_products[idx]
        favs = self.config_data.setdefault("favorites", [])
        # 중복 확인 (같은 사이트 + 이름)
        for f in favs:
            if f["site_name"] == p.site_name and f["name"] == p.name:
                messagebox.showinfo("알림", f"'{p.name[:30]}'\n이미 즐겨찾기에 있습니다.")
                return
        favs.append({
            "site_name": p.site_name,
            "name": p.name,
            "price": p.price,
            "unit_price": p.unit_price or "",
            "maker": p.extra_info.get("제조사", ""),
            "url": p.url,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        save_config(self.config_data)
        self._refresh_favorites()
        self.status_var.set(f"⭐ '{p.name[:25]}' 즐겨찾기 추가됨")

    # ────────────────────────────────
    # 사이트 관리
    # ────────────────────────────────
    def _refresh_site_list(self):
        self.site_tree.delete(*self.site_tree.get_children())
        for s in self.config_data.get("sites", []):
            username = s.get("credentials", {}).get("username", "")
            if s.get("requires_login"):
                login_info = f"🔒 {username}" if username else "🔑 미설정"
            else:
                login_info = "🔓 불필요"
            status = "✓ 활성" if s.get("enabled", True) else "✗ 비활성"
            builtin = "📌 " if s.get("builtin") else ""
            self.site_tree.insert("", "end", values=(
                builtin + s.get("name", ""), s.get("base_url", ""),
                s.get("crawler_type", "generic"), login_info, status
            ))

    def _get_selected_site_idx(self):
        sel = self.site_tree.selection()
        if not sel:
            messagebox.showinfo("알림", "사이트를 선택하세요")
            return None
        return self.site_tree.index(sel[0])

    def _add_site(self):
        SiteDialog(self, "사이트 추가")

    def _edit_site(self):
        idx = self._get_selected_site_idx()
        if idx is not None:
            SiteDialog(self, "사이트 수정", idx)

    def _edit_credentials(self):
        idx = self._get_selected_site_idx()
        if idx is None:
            return
        CredentialDialog(self, idx)

    def _delete_site(self):
        idx = self._get_selected_site_idx()
        if idx is None:
            return
        name = self.config_data["sites"][idx]["name"]
        if messagebox.askyesno("삭제 확인", f"'{name}' 사이트를 삭제하시겠습니까?"):
            self.config_data["sites"].pop(idx)
            save_config(self.config_data)
            self._refresh_site_list()

    def _test_login(self):
        """모든 사이트 로그인을 순차 테스트하고 결과를 하나의 팝업에 표시"""
        sites = self.config_data.get("sites", [])
        login_sites = [s for s in sites if s.get("credentials", {}).get("username")]

        if not login_sites:
            messagebox.showinfo("알림", "로그인 정보가 설정된 사이트가 없습니다.\n'🔑 로그인 설정'으로 먼저 설정하세요.")
            return

        self.status_var.set(f"🔐 로그인 테스트 중... ({len(login_sites)}개 사이트)")
        self.update_idletasks()

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = []

            for site in login_sites:
                name = site.get("name", "")
                try:
                    crawler = create_crawler(site)
                    try:
                        loop.run_until_complete(crawler.login())
                        if crawler.logged_in:
                            results.append(f"✅ {name}: 로그인 성공")
                        else:
                            results.append(f"❌ {name}: 로그인 실패")
                    finally:
                        loop.run_until_complete(crawler.close())
                except Exception as ex:
                    err_msg = str(ex)
                    results.append(f"❌ {name}: {err_msg}")

            loop.close()
            msg = "\n".join(results)
            self.after(0, lambda m=msg: self._show_login_results(m, len(login_sites)))

        threading.Thread(target=run, daemon=True).start()

    def _show_login_results(self, msg, count):
        """로그인 테스트 결과 팝업"""
        success = msg.count("✅")
        self.status_var.set(f"🔐 로그인 테스트 완료 — {success}/{count} 성공")
        title = f"로그인 테스트 결과 ({success}/{count})"
        if success == count:
            messagebox.showinfo(title, msg)
        else:
            messagebox.showwarning(title, msg)

    def _load_demo(self):
        import copy
        if self.config_data.get("sites") and not messagebox.askyesno("확인", "사용자 추가 사이트를 제거하고 데모를 불러올까요?\n(내장 사이트는 유지됩니다)"):
            return
        # 내장 사이트 유지 + 데모 추가
        builtin = [copy.deepcopy(s) for s in BUILTIN_SITES]
        demos = [
            {"name": "데모도매A", "enabled": True, "crawler_type": "demo",
             "base_url": "https://demo-a.example.com", "requires_login": True,
             "credentials": {"username": "demo", "password_encrypted": cred_mgr.encrypt("demo")},
             "login_config": SITE_TEMPLATE["login_config"].copy(), "selectors": {}, "extra_config": {}},
            {"name": "데모도매B", "enabled": True, "crawler_type": "demo",
             "base_url": "https://demo-b.example.com", "requires_login": True,
             "credentials": {"username": "demo", "password_encrypted": cred_mgr.encrypt("demo")},
             "login_config": SITE_TEMPLATE["login_config"].copy(), "selectors": {}, "extra_config": {}},
        ]
        # 기존 내장 사이트의 로그인 정보 보존
        for bs in builtin:
            for existing in self.config_data.get("sites", []):
                if existing.get("crawler_type") == bs["crawler_type"]:
                    bs["credentials"] = existing.get("credentials", bs["credentials"])
                    break
        self.config_data["sites"] = builtin + demos
        save_config(self.config_data)
        self._refresh_site_list()
        messagebox.showinfo("완료", "데모 사이트 2개가 추가되었습니다.\n내장 사이트의 로그인 정보는 유지됩니다.")

    def _save_settings(self):
        try:
            mx = int(self.max_results_var.get())
            to = int(self.timeout_var.get())
        except ValueError:
            messagebox.showerror("오류", "숫자를 입력하세요")
            return
        self.config_data.setdefault("settings", {})["max_results_per_site"] = mx
        self.config_data["settings"]["timeout_seconds"] = to
        save_config(self.config_data)
        messagebox.showinfo("저장", "설정이 저장되었습니다.")


# ═══════════════════════════════════════════════════════════════
# 6. 다이얼로그 — 사이트 추가/수정
# ═══════════════════════════════════════════════════════════════

class SiteDialog(tk.Toplevel):
    def __init__(self, parent: App, title: str, edit_idx=None):
        super().__init__(parent)
        self.parent = parent
        self.edit_idx = edit_idx
        self.title(title)
        self.geometry("560x620")
        self.configure(bg=App.BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        existing = parent.config_data["sites"][edit_idx] if edit_idx is not None else None

        container = tk.Frame(self, bg=App.BG, padx=25, pady=20)
        container.pack(fill="both", expand=True)

        row = 0
        def add_field(label, default=""):
            nonlocal row
            tk.Label(container, text=label, bg=App.BG, fg=App.TEXT, font=("맑은 고딕", 10)).grid(row=row, column=0, sticky="w", pady=6)
            var = tk.StringVar(value=default)
            tk.Entry(container, textvariable=var, width=40, bg=App.ENTRY_BG, fg=App.TEXT,
                     insertbackground=App.TEXT, relief="flat", font=("맑은 고딕", 10)).grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=6, ipady=4)
            row += 1
            return var

        self.name_var = add_field("사이트 이름", existing["name"] if existing else "")
        self.url_var = add_field("사이트 URL", existing.get("base_url", "") if existing else "https://")

        # 크롤러 유형
        tk.Label(container, text="크롤러 유형", bg=App.BG, fg=App.TEXT, font=("맑은 고딕", 10)).grid(row=row, column=0, sticky="w", pady=6)
        self.crawler_var = tk.StringVar(value=existing.get("crawler_type", "generic") if existing else "generic")
        crawler_combo = ttk.Combobox(container, textvariable=self.crawler_var, values=["generic", "demo"] + list(CUSTOM_CRAWLERS.keys()),
                                     state="readonly", width=15)
        crawler_combo.grid(row=row, column=1, sticky="w", padx=(10, 0), pady=6)
        row += 1

        # 로그인 필요 여부
        self.login_var = tk.BooleanVar(value=existing.get("requires_login", False) if existing else False)
        tk.Checkbutton(container, text="로그인 필요", variable=self.login_var, bg=App.BG, fg=App.TEXT,
                       selectcolor=App.BG3, activebackground=App.BG, activeforeground=App.TEXT,
                       font=("맑은 고딕", 10), command=self._toggle_login).grid(row=row, column=0, columnspan=2, sticky="w", pady=6)
        row += 1

        # 로그인 정보
        self.login_frame = tk.LabelFrame(container, text="  로그인 정보  ", bg=App.BG, fg=App.TEXT2,
                                          font=("맑은 고딕", 9, "bold"), padx=15, pady=10)
        self.login_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        lr = 0
        ec = existing.get("credentials", {}) if existing else {}
        el = existing.get("login_config", {}) if existing else {}

        tk.Label(self.login_frame, text="아이디", bg=App.BG, fg=App.TEXT, font=("맑은 고딕", 9)).grid(row=lr, column=0, sticky="w", pady=4)
        self.user_var = tk.StringVar(value=ec.get("username", ""))
        tk.Entry(self.login_frame, textvariable=self.user_var, width=25, bg=App.ENTRY_BG, fg=App.TEXT,
                 insertbackground=App.TEXT, relief="flat", font=("맑은 고딕", 10)).grid(row=lr, column=1, sticky="w", padx=10, ipady=3)
        lr += 1

        tk.Label(self.login_frame, text="비밀번호", bg=App.BG, fg=App.TEXT, font=("맑은 고딕", 9)).grid(row=lr, column=0, sticky="w", pady=4)
        self.pw_var = tk.StringVar()
        tk.Entry(self.login_frame, textvariable=self.pw_var, show="●", width=25, bg=App.ENTRY_BG, fg=App.TEXT,
                 insertbackground=App.TEXT, relief="flat", font=("맑은 고딕", 10)).grid(row=lr, column=1, sticky="w", padx=10, ipady=3)
        if existing and ec.get("password_encrypted"):
            self.pw_var.set("••••••••")  # 플레이스홀더
        lr += 1

        tk.Label(self.login_frame, text="로그인 URL", bg=App.BG, fg=App.TEXT, font=("맑은 고딕", 9)).grid(row=lr, column=0, sticky="w", pady=4)
        self.login_url_var = tk.StringVar(value=el.get("login_url", "/member/login"))
        tk.Entry(self.login_frame, textvariable=self.login_url_var, width=25, bg=App.ENTRY_BG, fg=App.TEXT,
                 insertbackground=App.TEXT, relief="flat", font=("맑은 고딕", 10)).grid(row=lr, column=1, sticky="w", padx=10, ipady=3)
        lr += 1

        tk.Label(self.login_frame, text="ID 필드명", bg=App.BG, fg=App.TEXT, font=("맑은 고딕", 9)).grid(row=lr, column=0, sticky="w", pady=4)
        lf = el.get("login_fields", {})
        id_field_name = list(lf.keys())[0] if lf else "user_id"
        self.id_field_var = tk.StringVar(value=id_field_name)
        tk.Entry(self.login_frame, textvariable=self.id_field_var, width=15, bg=App.ENTRY_BG, fg=App.TEXT,
                 insertbackground=App.TEXT, relief="flat", font=("맑은 고딕", 10)).grid(row=lr, column=1, sticky="w", padx=10, ipady=3)
        lr += 1

        tk.Label(self.login_frame, text="PW 필드명", bg=App.BG, fg=App.TEXT, font=("맑은 고딕", 9)).grid(row=lr, column=0, sticky="w", pady=4)
        pw_field_name = list(lf.keys())[1] if len(lf) > 1 else "password"
        self.pw_field_var = tk.StringVar(value=pw_field_name)
        tk.Entry(self.login_frame, textvariable=self.pw_field_var, width=15, bg=App.ENTRY_BG, fg=App.TEXT,
                 insertbackground=App.TEXT, relief="flat", font=("맑은 고딕", 10)).grid(row=lr, column=1, sticky="w", padx=10, ipady=3)
        lr += 1

        self._toggle_login()

        # 검색 셀렉터 (간략)
        sel_frame = tk.LabelFrame(container, text="  검색 CSS 셀렉터 (Generic 크롤러)  ", bg=App.BG, fg=App.TEXT2,
                                   font=("맑은 고딕", 9, "bold"), padx=15, pady=10)
        sel_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        es = existing.get("selectors", {}) if existing else {}
        self.sel_vars = {}
        for sr, (key, default) in enumerate([
            ("search_url_pattern", "/search?q={query}"),
            ("product_list", ".product-item"),
            ("product_name", ".product-name"),
            ("product_price", ".product-price"),
        ]):
            tk.Label(sel_frame, text=key, bg=App.BG, fg=App.TEXT2, font=("맑은 고딕", 8)).grid(row=sr, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=es.get(key, default))
            tk.Entry(sel_frame, textvariable=v, width=30, bg=App.ENTRY_BG, fg=App.TEXT,
                     insertbackground=App.TEXT, relief="flat", font=("맑은 고딕", 9)).grid(row=sr, column=1, sticky="w", padx=10, ipady=2)
            self.sel_vars[key] = v

        # 버튼
        btn_frame = tk.Frame(container, bg=App.BG)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text="💾 저장", style="Green.TButton", command=self._save).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="취소", style="Flat.TButton", command=self.destroy).pack(side="left")

        container.columnconfigure(1, weight=1)

    def _toggle_login(self):
        state = "normal" if self.login_var.get() else "disabled"
        for child in self.login_frame.winfo_children():
            try:
                child.configure(state=state)
            except:
                pass

    def _save(self):
        name = self.name_var.get().strip()
        url = self.url_var.get().strip()
        if not name or not url:
            messagebox.showwarning("알림", "사이트 이름과 URL은 필수입니다", parent=self)
            return

        site = json.loads(json.dumps(SITE_TEMPLATE))
        site["name"] = name
        site["base_url"] = url
        site["crawler_type"] = self.crawler_var.get()
        site["requires_login"] = self.login_var.get()

        if self.login_var.get():
            site["credentials"]["username"] = self.user_var.get().strip()
            pw = self.pw_var.get()
            if pw and pw != "••••••••":
                site["credentials"]["password_encrypted"] = cred_mgr.encrypt(pw)
            elif self.edit_idx is not None:
                # 비밀번호 미변경 → 기존 유지
                old = self.parent.config_data["sites"][self.edit_idx]
                site["credentials"]["password_encrypted"] = old.get("credentials", {}).get("password_encrypted", "")

            site["login_config"]["login_url"] = self.login_url_var.get()
            site["login_config"]["login_fields"] = {
                self.id_field_var.get(): "{username}",
                self.pw_field_var.get(): "{password}",
            }

        for key, var in self.sel_vars.items():
            site["selectors"][key] = var.get()

        if self.edit_idx is not None:
            # 수정 — 기존의 enabled 상태 및 builtin 표시 유지
            old_site = self.parent.config_data["sites"][self.edit_idx]
            site["enabled"] = old_site.get("enabled", True)
            if old_site.get("builtin"):
                site["builtin"] = True
            self.parent.config_data["sites"][self.edit_idx] = site
        else:
            self.parent.config_data.setdefault("sites", []).append(site)

        save_config(self.parent.config_data)
        self.parent._refresh_site_list()
        self.destroy()


# ═══════════════════════════════════════════════════════════════
# 7. 다이얼로그 — 로그인 정보 설정
# ═══════════════════════════════════════════════════════════════

class CredentialDialog(tk.Toplevel):
    def __init__(self, parent: App, site_idx: int):
        super().__init__(parent)
        self.parent = parent
        self.site_idx = site_idx
        site = parent.config_data["sites"][site_idx]
        self.title(f"🔑 로그인 설정 — {site['name']}")
        self.geometry("420x280")
        self.configure(bg=App.BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        c = tk.Frame(self, bg=App.BG, padx=30, pady=25)
        c.pack(fill="both", expand=True)

        creds = site.get("credentials", {})

        tk.Label(c, text=f"사이트: {site['name']}", bg=App.BG, fg=App.ACCENT,
                 font=("맑은 고딕", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))

        tk.Label(c, text="아이디", bg=App.BG, fg=App.TEXT, font=("맑은 고딕", 10)).grid(row=1, column=0, sticky="w", pady=6)
        self.user_var = tk.StringVar(value=creds.get("username", ""))
        tk.Entry(c, textvariable=self.user_var, width=28, bg=App.ENTRY_BG, fg=App.TEXT,
                 insertbackground=App.TEXT, relief="flat", font=("맑은 고딕", 11)).grid(row=1, column=1, padx=10, ipady=5)

        tk.Label(c, text="비밀번호", bg=App.BG, fg=App.TEXT, font=("맑은 고딕", 10)).grid(row=2, column=0, sticky="w", pady=6)
        self.pw_var = tk.StringVar()
        tk.Entry(c, textvariable=self.pw_var, show="●", width=28, bg=App.ENTRY_BG, fg=App.TEXT,
                 insertbackground=App.TEXT, relief="flat", font=("맑은 고딕", 11)).grid(row=2, column=1, padx=10, ipady=5)

        if creds.get("password_encrypted"):
            masked = cred_mgr.mask(get_site_password(site))
            tk.Label(c, text=f"현재 저장된 비밀번호: {masked}", bg=App.BG, fg=App.TEXT2,
                     font=("맑은 고딕", 8)).grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 10))

        btn_f = tk.Frame(c, bg=App.BG)
        btn_f.grid(row=4, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_f, text="💾 저장", style="Green.TButton", command=self._save).pack(side="left", padx=(0, 10))
        ttk.Button(btn_f, text="취소", style="Flat.TButton", command=self.destroy).pack(side="left")

    def _save(self):
        site = self.parent.config_data["sites"][self.site_idx]
        user = self.user_var.get().strip()
        pw = self.pw_var.get()

        if user:
            site.setdefault("credentials", {})["username"] = user
        if pw:
            site.setdefault("credentials", {})["password_encrypted"] = cred_mgr.encrypt(pw)

        site["requires_login"] = bool(user)
        save_config(self.parent.config_data)
        self.parent._refresh_site_list()
        messagebox.showinfo("저장 완료", f"'{site['name']}' 로그인 정보가 저장되었습니다.\n암호화: {cred_mgr.method}", parent=self)
        self.destroy()


# ═══════════════════════════════════════════════════════════════
# 8. 메인
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = App()
    app.mainloop()
