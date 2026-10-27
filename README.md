# 도매 최저가 비교 프로그램

여러 약품 도매 사이트에서 특정 제품의 최저가를 동시 검색하는 프로그램입니다.
Windows 데스크탑 앱과 웹 버전(브라우저) 두 가지로 실행할 수 있습니다.

## 현재 버전: v8.1

### 버전 정책
- 기능 추가/변경 → 정수 버전업 (예: 1.0 → 2.0)
- 사이트 추가 → 소수점 버전업 (예: 1.0 → 1.1)

## 내장 지원 사이트 (15개)
| 사이트 | 기술 스택 | 로그인 방식 |
|--------|-----------|-------------|
| 바로팜 | React SPA + REST | Token 인증 |
| 유팜몰 | ASP.NET WebForms (로그인/검색/목록 파싱 확인됨) | ViewState POST |
| 한미몰 | Spring + DWR (실계정 로그인/검색 확인됨, www 도메인 필수) | DWR 특수 포맷 + DWRSESSIONID 핸드셰이크 |
| 플랫팜 | Next.js + NextAuth | JWT |
| 새로팜 | Cookie 기반 (로그인/검색/목록 파싱 확인됨) | Base64 비밀번호 + OTP 2단계 |
| 팜뉴트리션 | 그누보드 PHP (Tailwind 리뉴얼, 검색 URL 확인됨) | 폼 POST |
| 드시모네 | Cafe24 (로그인/검색 확인됨) | multipart/form-data + 동적 토큰 |
| 팜스트리트 | JSP | 폼 POST |
| 대웅더샵 | Next.js SSR + SSO (로그인/검색 확인됨) | JSON POST → SSO 리다이렉트 |
| 동아DAPmall | 개별 크롤러 (로그인/검색/파싱 전 항목 검증 완료) | 폼 POST (평문, userId/userPw) |
| 서울약사신협 | Classic ASP (로그인/검색 확인됨) | 폼 POST (평문, 암호화 여부 미확인) |
| 스마트팜 | Classic ASP (로그인/검색/목록 파싱 확인됨) | 폼 POST (평문, 암호화 없음) |
| 광동몰 | Java 서버 렌더링 (로그인/검색/재고 확인됨) | 폼 POST (평문, xpw 필드) |
| 동성몰 | NHN Commerce(고도몰5, moment 스킨) (검색/목록 파싱 실캡쳐 확인됨) | AJAX 폼 POST (평문) |
| 팜페이몰 | ASP.NET + 자체 JDINS 프레임워크 (로그인/검색 실캡쳐 확인됨) | AJAX POST /loginChk.json (평문 userid/userpwd) |

> 대웅더샵(`DaewoongTheShopCrawler`)/동아DAPmall(`DapMallCrawler`)은 v2.4에서
> 공유 GenericCrawler 대신 전용 크롤러 클래스로 분리됐습니다. 이제 내장
> 사이트 전부 자기 자신만의 크롤러 클래스를 가지며, 로그인/검색 스펙도
> DevTools 실캡쳐로 확인되어 있습니다. 단, v7.2에서 추가된 동성몰의 로그인은
> 실캡쳐가 아니라 공개 로그인 폼/JS로 확인했습니다(각 크롤러 docstring 참고).
>
> 대웅더샵은 로그인 도메인(www.shop.co.kr)과 서비스 도메인(the.shop.co.kr)이
> 분리된 SSO 구조입니다: `POST https://www.shop.co.kr/front/api/auth/mimsLogin`
> (JSON, 필드 identifier/password/clientIP/redirectUrl)으로 로그인하면 즉시
> 세션 쿠키를 주지 않고 `{"data": "https://mims-account.shop.co.kr/login/direct?ot=..."}`
> 형태의 SSO 리다이렉트 URL을 반환합니다. 이 URL은 "중간 페이지"가 아니라
> 정적 export된 Next.js SPA 셸이라 서버 HTML에는 리다이렉트 정보가 전혀
> 없습니다(v3.5에서 JS 번들 역공학으로 확인). 실제 로그인 완료는 이 페이지의
> JS가 호출하는 `GET https://mims-account.shop.co.kr/apis/auth/login/direct
> ?ot=<토큰>` API를 직접 호출하고, 반환되는 `data.redirectURLWithStNMk`를
> 한 번 더 GET해야 the.shop.co.kr 세션이 완성되는 구조입니다. 검색 결과는
> 검색 페이지 HTML에 없고(브라우저가 로드 후 별도 API로 불러옴), v7.4부터
> `POST https://sonic-feapi.shop.co.kr/userfe/api/v1/userfe/main/search/groups`를
> `userAccessToken` 쿠키 값으로 `Authorization: Bearer` 인증해 직접 호출합니다
> (요청·응답 형식은 사이트 JS 역공학으로 확인). clientIP 값이
> 실제 IP가 아니어도 로그인되는지는 미확인이라, 크롤러가 ipify로 실행 PC의
> 공인 IP를 조회해 채웁니다.
>
> 동아DAPmall은 DevTools 실캡쳐로 로그인(`POST /auth/login`, 필드 siteId/
> userId/userPw, 평문 전송)과 검색(`GET /prod/search-list/?keywordType=ALL
> &keyword={query}&keywordMktSeq=`), 검색 결과 상품 li 구조(`li[data-pid]`,
> `.prod_name`, `.price .selling strong`), 로그인 성공(302 리다이렉트)/
> 실패(200 + 폼 재렌더링) 판별까지 전부 확인되어 정상 동작합니다. 상품
> 클릭 시 페이지 이동 없이 `POST /prod/detail/{pid}` JSON 팝업으로 뜨는
> 구조라 GET 상세페이지가 없어, 상품 링크는 검색결과 페이지 URL로 대체.
>
> 스마트팜은 로그인(`POST /Login/Login_Proc.asp`), 검색(`GET /Goods/Goods_List.asp`),
> 상품 목록 결과 HTML 구조까지 모두 확인되어 전용 크롤러(`SmartPharmCrawler`)로
> 정상 동작합니다. 응답 페이지가 EUC-KR이라 인코딩 지정 없이 읽으면
> `UnicodeDecodeError`가 나므로 모든 응답을 `encoding="euc-kr"`로 읽습니다.
> v2.9에서 DevTools로 재확인해보니 실제 로그인 처리 엔드포인트는
> `/Login/Login_Proc.asp`였고(`/Login/Login.asp`는 폼이 표시되는 페이지일
> 뿐), 기존 코드는 `Login.asp`에 그대로 POST하고 있어 실제로는 로그인이
> 되지 않고 있었습니다. 홈페이지 네비게이션에 "로그아웃" 문자열이 로그인
> 여부와 무관하게 항상 존재해 로그인 성공 판정 로직이 이를 성공으로
> 오판, 예외 없이 비로그인 세션으로 검색이 진행되어 결과가 조용히 0건으로
> 나오던 것으로 추정됩니다.
>
> 유팜몰은 메인 페이지(`default.aspx`)에서 `__VIEWSTATE`를 추출해 같은 URL로
> 포스트백하는 클래식 ASP.NET WebForms 로그인이며, 검색(`GET
> /Search/Search.aspx?keyword={query}`)과 상품 목록 HTML 구조(`#tbodyProdList
> tr[data-idx]` 안의 `span[id*="lblProductName"/"lblPrice"/"lblStandard"]`)까지
> 확인되어 전용 크롤러(`UPharmMallCrawler`)로 정상 동작합니다. v3.0에서
> DevTools로 재확인해보니 로그인 응답 HTML에 "mypage"/"logout" 문자열이
> 비로그인 상태에도 항상 포함돼 있어(정적 "/Mypage/..." 링크들, `Logout()`
> 함수의 "/Member/LogOut.aspx" 참조) 기존 판정 로직이 로그인 실패도 항상
> 성공으로 오판, 실제로는 비로그인 세션으로 검색이 진행되어 결과가 조용히
> 0건으로 나오던 것으로 추정됩니다. 서버가 실제 로그인 여부에 따라 다르게
> 렌더링하는 `var isLogin = "true"/"false";` 값으로 판정하도록 수정했습니다.
>
> 새로팜은 로그인(`POST /front/ajax/login/loginCheckAjaxEncrypt.do`, JSON
> {userId, userPw(base64), userAgent, cookieUserIdChk})과 검색(`GET
> /w/product/searchProductList.do?mainSchValue={query}`), 상품 목록 HTML
> 구조(`div.prd-item[data-no]` 안의 `p.name`/`p.text`/`p.amount`)까지
> 확인되어 전용 크롤러(`SaeroPharmCrawler`)로 정상 동작합니다. v3.1에서
> DevTools로 재확인해보니 1단계 로그인 응답의 `flag=="4"`는 아이디/비밀번호
> 확인만 통과했다는 뜻일 뿐, 응답에 같이 오는 `returnUrl`(OTP 토큰 포함
> `loginCheckUsingEncryptOTP.do?...`)을 한 번 더 GET해야 실제 인증 세션이
> 완성되는 2단계 SSO 구조였습니다(대웅더샵과 동일 패턴). 기존 코드는
> flag=="4"만 보고 바로 로그인 성공 처리해 실제 세션은 완성되지 않았고,
> 사이트가 비로그인 요청에는 "로그인이 필요합니다" 알럿만 띄우고 상품
> 목록을 아예 내려주지 않아 ID/PW를 정확히 입력해도 검색이 조용히 0건이
> 되던 것으로 확인됐습니다. `returnUrl` GET을 로그인 절차에 추가했습니다.
>
> 팜뉴트리션은 그누보드(PHP) 기반 쇼핑몰이 Tailwind 기반 테마로 전면
> 개편되면서 검색 목록 URL이 `/shop/list_all.php?stx=`에서
> `/shop/search.php?q=`로 바뀌어 있었습니다. `PharmNutritionCrawler`는
> 여전히 옛 URL/파라미터로 요청하고 있어 상품 링크(`it_id`)를 하나도 못
> 뽑고 조용히 0건이 되던 것으로 v3.2에서 DevTools로 재확인해 수정했습니다.
> 상품 상세 페이지(`item.php?it_id=`)의 `sit_title`/`it_price`/
> `it_send_cost_display` 구조는 리뉴얼 후에도 동일하게 유지되고 있어 해당
> 파싱 로직은 그대로 재사용합니다.
>
> 드시모네(Cafe24)는 로그인이 항상 실패하고 있었습니다. v3.6에서 DevTools로
> 실제 로그인 요청을 재캡쳐한 결과 세 가지가 틀려 있었습니다: (1) `sLoginKey`는
> 로그인 페이지에 박힌 고정값이 아니라 `GET /exec/front/Member/loginKey`에서
> 시도마다 새로 발급받는 토큰(`{"sKey":"..."}`)인데 기존 코드는 페이지
> HTML/스크립트에서 정규식으로 찾으려 해 항상 빈 문자열이었음, (2) 실제 폼에는
> 있는 필수 필드 `member_login_csrf`(JWT, 로그인 페이지의 hidden input)가
> 기존 코드엔 아예 없었음, (3) `sIsSnsCheckid`/`ch_ref` 필드에 실수로 다음
> 필드명 문자열 `"sProvider"`/`"checkoutToken"`을 값으로 넣고 정작
> `sProvider`/`checkoutToken` 필드 자체는 빠져 있었음. 세 가지 모두 수정해
> `DesimoneCrawler`가 정상 동작합니다. 단, v3.7에서 다시 확인해보니
> `member_login_csrf`는 로그인 페이지 hidden input이 아니라 페이지 JS가
> `POST /shop1/api/member/LoginSaveid`(body `&mode=logoff`) 응답의
> `data.csrf_token`을 폼에 주입하는 값이었고, v3.6은 이를 HTML에서 찾아 항상
> 빈 토큰을 보내 HTTP 403을 받고 있었습니다(이를 성공으로 오판). 토큰 발급
> 경로를 고쳤습니다. 검색(`GET
> /product/search.html?keyword={query}`)과 상품 목록 HTML 구조(`a.name`
> 안의 span, `li[rel="판매가"]` 등)는 기존에 이미 정확했습니다.
>
> 서울약사신협은 사용자가 직접 확인한 로그인(`POST /member/login_chk.asp`)/
> 검색(`GET /order/order_goods.asp`) 스펙으로 전용 크롤러(`CupharmCrawler`)가
> 구현되어 있습니다. 비밀번호 클라이언트측 AES 암호화 여부만 미확인 상태로,
> 우선 평문 전송합니다. 응답 페이지 인코딩이 v2.2 확인 당시엔 cp949(EUC-KR
> 상위호환)였으나 이후 사이트 측에서 UTF-8로 바뀐 것으로 보여(v2.8에서
> 검색결과 한글 깨짐으로 발견), 이제는 cp949로 고정하지 않고 UTF-8을 먼저
> 시도한 뒤 실패할 때만 cp949로 폴백합니다.

> 광동몰(광동제약 약국전용 폐쇄몰)은 v7.1에서 실계정 DevTools 캡처로 확인한 스펙으로
> 전용 크롤러(`KDShopCrawler`)가 추가됐습니다. 로그인은 `POST /member/login_act.do`
> (필드 `id`/`xpw`, 평문 — 페이지 JS가 비밀번호를 `pw`에서 `xpw`로 옮겨 보냄)이며,
> 로그인 화면의 Google reCAPTCHA는 클라이언트 검사뿐이라 실제 제출값에
> `g-recaptcha-response`가 없습니다(서버 미검증). 성공 시 본문은
> `parent.location.href='/main/index.do'` 스크립트이고 `MEMBER_TOKEN`(JWT) 쿠키가
> 발급됩니다. 검색은 `GET /goods/category.do?stype=all&sword={query}`(비로그인이면
> 302)이고, 상품은 `li.item[gno]` 안의 `input#gName{gno}`/`input#gPrice{gno}` 값으로
> 파싱합니다. 목록엔 재고가 없어 상세 `GET /goods/list_detail.do?gno=`의 업체별
> `tr[data-stock]`으로 품절을 판정합니다(검색당 최대 10건 추가 요청).

## 주요 기능
- 🔍 여러 사이트 동시 검색 및 가격 비교
- 🔒 비밀번호 AES(Fernet) 암호화 저장
- ⭐ 즐겨찾기 탭
- 📝 메모장 탭 (암호화 저장)
- 🖱️ 우클릭 컨텍스트 메뉴 (복사/즐겨찾기)
- 🔗 더블클릭 → 해당 사이트 상품 검색 페이지 오픈
- 🚫 품절 제외 체크박스 (검색 결과에서 품절 상품 숨김, 설정 유지)
- 🖼 결과 이미지(썸네일) 표시 — 검색 바의 "이미지 숨기기/보기" 버튼으로 토글, 설정 유지
  (JPEG 표시는 Pillow 필요: `pip install pillow`, 없으면 PNG/GIF만 표시)
- ☀️ 밝은 톤 UI 테마 (v8.0)

## 진단 파일(debug/) 취급
- 검색/로그인 오류 시 프로그램 폴더의 `debug/`에 사이트 응답이 저장됩니다.
  로그인 상태 페이지라 약국명·계정 정보가 들어 있을 수 있습니다.
- **저장소에 올리지 마세요.** 분석이 필요하면 채팅에 파일을 직접 첨부하세요.
  (`.gitignore`로 제외되며, 웹 업로드로 올라오면 `Block sensitive files` 검사가 실패합니다)

## 실행 방법
### 데스크탑 앱
```bash
pip install -r requirements.txt
python wholesale_price_finder_v8.1.py
```

### 웹 버전 (브라우저)
```bash
pip install -r requirements.txt
python web/server.py          # http://127.0.0.1:8000 이 자동으로 열림
```
- 데스크탑 앱의 기능(검색·정렬·품절 제외·우클릭 메뉴·즐겨찾기·사이트 수정/삭제·
  로그인 설정·로그인 테스트·데모 불러오기·암호화 메모장·설정)을 전부 브라우저에서 사용.
  추가로 사이트 활성/비활성 체크박스, 진단 파일(debug/) 목록·다운로드·삭제 제공.
- 크롤러는 데스크탑 파일(`wholesale_price_finder_v*.py` 중 최신 버전)을 그대로 불러와
  서버에서 실행합니다(도매 사이트는 브라우저에서 직접 호출 불가 — CORS/쿠키 제약).
- `config.json`·`memo.dat`·암호화 키(`~/.wholesale_finder_key`)를 데스크탑 앱과 공유하므로
  번갈아 써도 됩니다. 서버엔 tkinter가 없어도 실행됩니다.

| 옵션 | 환경변수 | 기본값 | 설명 |
|------|----------|--------|------|
| `--host` | `WPF_HOST` | `127.0.0.1` | `0.0.0.0`이면 외부 접속 허용 |
| `--port` | `WPF_PORT` | `8000` | |
| `--password` | `WPF_WEB_PASSWORD` | 없음 | 접속 비밀번호 (외부 공개·서버 배포 시 필수) |
| `--data-dir` | `WPF_DATA_DIR` | 프로그램 폴더 | config.json/memo.dat/debug 저장 위치 |
| `--no-browser` | | | 시작 시 브라우저 자동 열기 끔 |

> 현재 웹 버전은 **1인용**입니다(설정·계정 정보가 서버에 하나만 저장). 여러 사람이 쓰는
> 서버로 배포하려면 사용자별 계정/설정 분리가 추가로 필요합니다.

## exe 변환
```bash
pip install pyinstaller
pyinstaller --onefile --windowed wholesale_price_finder_v8.1.py
```

## 변경 이력
- v8.1 — 팜페이몰: 결과가 있는 제품도 '오류'로 뜨던 문제 수정. 검색 응답 `rtnCode`가 "OK"가
  아니면 전부 오류 처리했으나, 사이트 JS(`Jdins.sendAjaxJson`)는 `rtnCode=="ERR"`만 오류로 봄.
  상품 배열이 있으면 성공, 상품이 없을 때만 ERR/E코드를 오류로 표시(E9999는 세션 종료 안내).
  응답 BOM 허용, 2페이지 이후 실패 시 1페이지 결과 유지, 가격·재고 "180.00"/"1,200" 형태 변환.
- v8.0 — UI 개선 2건(데스크탑 앱). 전체 테마를 어두운 남색 계열에서 밝은 톤(연회색 배경·
  흰 카드/표·진한 글자)으로 변경하고 입력창·메모장·요약 카드에 얇은 테두리 추가.
  검색 결과 표에 상품 이미지(썸네일) 열 추가 — 검색 바의 "🖼 이미지 숨기기/보기" 버튼으로
  재검색 없이 켜고 끄며, 상태는 `config.json`의 `settings.show_images`에 저장. 이미지는 결과
  표시 후 백그라운드에서 받아 오고(동시 8개, 10초 제한) 캐시해 정렬·품절 제외·토글 시 다시
  받지 않음. JPEG는 Pillow가 있어야 표시(없으면 PNG/GIF만, 상태줄에 안내). 웹 버전은 변경 없음.
- v7.4 — 실사용 오류 3건 수정. 동성몰: 검색 결과가 없을 때 사이트 문구("상품이
  존재하지 않습니다.", `div.goods_no_data`)를 못 알아봐 0건을 "구조 변경" 오류로
  띄우던 문제 수정. 대웅더샵: 검색 페이지가 상품 목록을 HTML이 아니라 로드 후
  별도 API(`sonic-feapi.shop.co.kr/.../main/search/groups`, `userAccessToken`
  Bearer 인증)로 불러오는 구조라 HTML 파싱으로는 항상 실패하던 검색을 API 직접
  호출로 교체. 팜페이몰 "로그인은 되는데 검색이 안 됨" 수정. 로그인 확인 페이지가 JS로
  심는 `loginHash`·`userCode` 쿠키가 앱에서 빠져 검색이 `/logOutDiscon.json`으로
  튕기던 문제. 같은 쿠키를 직접 설정하고, 세션이 끊기면 0건 대신 오류로 표시.
- v7.3 — 사이트 추가: 팜페이몰(pharmpaymall.com). ASP.NET + 자체 JDINS 프레임워크.
  로그인(POST `/loginChk.json`, 필드 `userid`/`userpwd`, 응답 `returnMapper.rtnCode`
  == "OK" 성공 → `rtnURL` `/login_confirm.aspx` 이동)과 검색(POST
  `/usr/UPT/UPT001R1.json`, form 값 `pageInfo`/`formData`가 JSON 문자열, 응답
  `goodsnm`/`stand`/`syncodenm`/`minprice`/`stocksum`)은 실계정 DevTools 캡쳐로 확인.
  상품 상세 GET 주소는 미확인이라 링크는 사이트 홈(내장 15개).
- v7.2 — 사이트 추가: 동성몰(dspmall.kr). NHN Commerce(고도몰5, moment 스킨) 기반
  B2B 발주몰. 로그인(AJAX POST `/member/login_ps.php`, 필드 `loginId`/`loginPwd`,
  실패 시 응답 JSON에 `code`/`message`)은 공개 폼·JS로 확인. 검색(GET
  `/goods/goods_search.php?keyword=`)과 결과 구조(`div.item_cont` > `.item_name`/
  `.item_price`, 이미지는 lazy-load라 `data-original`)는 실계정 DevTools 캡쳐로
  확인. 품절은 `li.item_soldout`/`.item_soldout_bg`/아이콘 `alt="품절"`로 판정(내장 14개).
- v7.1 — 광동몰(kdshop.co.kr) 추가(전용 크롤러 `KDShopCrawler`). 로그인·검색·재고
  조회 스펙은 실계정 DevTools 캡처로 확인.
- v7.0 — 사이트 관리 탭의 "사이트 추가" 버튼 제거(데스크탑·웹). 사이트마다 로그인·
  크롤링 방식이 달라 사이트는 내장 크롤러로만 추가. 수정/로그인 설정/삭제는 유지.
- v6.0 — 웹 버전 추가(`web/server.py` + `web/static/`). 데스크탑 앱의 크롤러·설정·
  암호화 코드를 그대로 재사용해 모든 기능을 브라우저에서 제공. 선택적 접속 비밀번호,
  데이터 폴더 지정, 진단 파일 다운로드 지원. 데스크탑 앱 동작 변경 없음.
- v5.0 — 검색 탭에 "품절 제외" 체크박스 추가. 켜면 품절 상품을 결과 테이블과
  요약 카드(총 결과/최저가)에서 제외하며 재검색 없이 즉시 적용. 상태는
  `config.json`의 `settings.hide_soldout`에 저장.
- v4.2 — 쿠키를 브라우저처럼 따옴표 없이 전송(`CookieJar(quote_cookie=False)`).
  aiohttp 기본 동작은 `=`가 든 쿠키를 `JSESSIONID="...="`로 감싸 보내 팜스트리트
  서버가 매 요청 새 세션을 발급 → 로그인 직후 세션이 사라져 검색이 '오류'였음.
  팜스트리트 로그인 실패 시 요청 흐름(쿠키 값 마스킹)을 `debug/`에 저장.
- v4.1 — 검색 결과를 해석하지 못하면 응답을 `debug/` 폴더에 저장(진단 파일)하고
  경로를 오류 메시지에 표시. 팜스트리트: 로그인 후 `/main` 접근으로 실제 세션 검증,
  retCd=C(비밀번호 변경 권유) 세션 제한 안내, 검색 폼 hidden 필드 그대로 전송.
  대웅더샵: App Router 재배포로 바뀐 CSS 해시 대응(클래스 접두사 매칭), RSC
  페이로드 파싱 폴백 추가.
- v4.0 — 스마트팜 검색이 로그인 상태에서도 항상 0건이던 버그 수정. 브라우저는
  `POST /Goods/Goods.asp` → (iframe) `GET /Goods/Goods_List.asp`(Referer=Goods.asp)
  2단계인데 앱은 `Goods_List.asp`만 호출하고 있었음(사용자 DevTools 캡처로 확인).
  브라우저와 같은 흐름으로 변경하고, 서버 오류 응답은 HTTP 상태로 표시.
- v3.9 — 한미몰 "DWR 세션 발급 실패" 수정: `hmpmall.co.kr` → `www.hmpmall.co.kr`
  301 리다이렉트가 새로 생겨 DWR POST 본문이 유실되던 문제(서버 응답 "Failed to
  find parameter: batchId")를 www 주소 직접 사용으로 해결, 성공 판정을 사이트
  JS와 같은 `isReceived` 기준으로 변경. 드시모네 로그인에 브라우저와 같은 `CheckCaptcha` 확인 단계 추가(캡차
  필요 시 원인 안내). 사이트 JS 재확인 결과 https에서는 비밀번호를 평문 그대로
  제출하므로 앱 요청은 브라우저와 동일 — 실패는 계정 정보 문제이며, 간편로그인
  (카카오/네이버 등) 가입 계정은 ID/PW 로그인이 불가함을 오류 메시지로 안내.
- v3.8 — 실계정 로그인 테스트(8/12)와 '유산균' 검색에서 확인된 오류 수정.
  대웅더샵: SSO 토큰 API 원본 응답 키가 `data`인데 `responseData`를 찾아 최종
  이동 주소를 못 찾던 버그 수정(실계정도 로그인 실패하던 원인), 로그인 판정을
  the.shop.co.kr 홈이 로그아웃 페이지로 307되는지로 변경. 팜스트리트: 사이트
  JS가 성공으로 처리하는 `retCd=C`(비밀번호 변경 권유)를 실패로 보던 문제
  수정("로그인 실패: Success"). 바로팜: API의 null 필드로 검색 전체가
  `NoneType.strip` 오류 나던 문제 수정. 스마트팜/팜스트리트/대웅더샵: 로그인
  세션이 없을 때 조용한 0건 대신 오류 표시.
- v3.7 — 전 사이트 '마스크' 검색 + 더미(틀린) 계정 라이브 테스트로 찾은 로그인
  판정 버그 일괄 수정. 한미몰: DWR CSRF 핸드셰이크(`__System.generateId` →
  `DWRSESSIONID`) 누락으로 맞는 계정도 로그인이 안 되던 문제 수정, 실패 판정을
  `auth:null`/message 기준으로 변경. 팜뉴트리션: 실패(alert) 응답을 성공으로
  오판하던 판정 수정 + 상품 `it_id`(예: `Z-HF016`)를 숫자만 받던 정규식 때문에
  검색이 항상 0건이던 버그 수정. 드시모네: `member_login_csrf`를
  `LoginSaveid` API에서 받도록 수정(v3.6은 항상 빈 토큰 → 403을 성공으로 오판).
  대웅더샵: 실패 사유가 빈 문자열로 보이던 문구 보완. 계정 미설정 사이트는
  조용히 0건 대신 "로그인 정보 미설정" 오류로 표시.
- v3.6 — 드시모네(hsaless.cafe24.com) 로그인이 항상 실패하던 버그 수정.
  DevTools로 실제 로그인 요청을 재캡쳐한 결과 세 가지가 틀려 있었음:
  (1) `sLoginKey`는 로그인 페이지에 박힌 고정값이 아니라
  `/exec/front/Member/loginKey`에서 시도마다 새로 발급받는 토큰인데 기존
  코드는 페이지 HTML/스크립트에서 정규식으로 찾으려 해 항상 빈
  문자열이었음, (2) 실제 폼에는 있는 필수 필드 `member_login_csrf`(JWT,
  로그인 페이지의 hidden input)가 기존 코드엔 아예 없었음, (3)
  `sIsSnsCheckid`/`ch_ref` 필드에 실수로 다음 필드명 문자열
  `"sProvider"`/`"checkoutToken"`을 값으로 넣고 정작 `sProvider`/
  `checkoutToken` 필드 자체는 빠져 있었음. 세 가지 모두 수정 — loginKey
  발급 요청 추가, `member_login_csrf` 추출/전송 추가, 필드 구성을 실제
  캡처와 동일하게 정리.
- v3.5 — 대웅더샵 로그인이 실제로는 항상 실패 처리되던 버그 수정.
  mimsLogin 성공 응답의 SSO 리다이렉트 URL(`mims-account.shop.co.kr/
  login/direct?ot=...`)이 정적 export된 Next.js SPA 셸이라 서버 HTML에
  리다이렉트 정보가 전혀 없어, 기존의 HTML 스크래핑 기반 리다이렉트 추적
  로직이 애초에 성립할 수 없는 구조였음. JS 번들 역공학으로 실제로는
  `GET mims-account.shop.co.kr/apis/auth/login/direct?ot=<토큰>` API를
  호출해야 함을 확인하고, 반환되는 `redirectURLWithStNMk`를 GET하도록
  로그인 로직을 교체. 무효 토큰 실패 응답 형태는 직접 테스트로 확인했으나
  샌드박스에 실 계정이 없어 성공 경로 최종 확인은 실 계정 테스트 필요.
- v3.4 — 스마트팜 로그인이 실제로는 항상 실패 처리되던 버그 수정. 로그인
  폼이 화면에 안 보이는 iframe(`Login_iFrm`)으로 제출되는 구조라 응답에
  "Logout.asp"/"로그아웃" 같은 페이지 텍스트가 아예 없어서 기존 판정이 항상
  실패로 오판하고 있었음. 사용자가 실제 계정으로 성공/실패 응답을 직접
  캡처해 확인: 성공 시 `parent.location.replace('/')`(부모 창 이동), 실패
  시 `alert('아이디 또는 비밀번호가 잘못되었습니다.')`만 뜸. 판정 기준을
  `parent.location.replace(` 포함 여부로 교체.
- v3.3 — 유팜몰 로그인이 실제로는 항상 실패 처리되던 버그 수정. 사용자가
  실제 계정(정상/의도적 오입력 비밀번호)으로 직접 재현해 DevTools로 확인한
  결과, v3.0에서 도입한 `isLogin = "true"/"false"` 판정 기준이 애초에 틀린
  전제였음 — 페이지 소스에 그냥 "false"로 고정된 placeholder라 정상
  로그인해도 바뀌지 않음. 실제 성공/실패는 응답에 포함되는 리다이렉트
  스크립트로 구분됨: 성공 시 `location.href='/?type=2'`, 실패 시 리다이렉트
  없이 alert만 뜸. 판정 기준을 이 리다이렉트 존재 여부로 교체.
- v3.2 — 팜뉴트리션(pharmnutrition.co.kr) 검색 결과 0건 버그 수정. 사이트가
  Tailwind 기반 테마로 전면 개편되면서 검색 목록 URL이
  `/shop/list_all.php?stx=`에서 `/shop/search.php?q=`로 바뀌어 있었는데
  `PharmNutritionCrawler`는 여전히 옛 URL/파라미터로 요청하고 있어 상품
  링크(`it_id`)를 하나도 못 뽑고 조용히 0건이 되던 것으로 확인됨(DevTools로
  재확인). 상품 상세 페이지(`item.php?it_id=`)의 `sit_title`/`it_price`/
  `it_send_cost_display` 구조는 리뉴얼 후에도 그대로 유지되고 있어 해당
  파싱 로직은 변경 없음. `SEARCH_URL`과 쿼리 파라미터명을 새 엔드포인트로
  수정.
- v3.1 — 새로팜(saeropharm.com) 로그인이 실제로는 안 되고 있던 버그 수정.
  DevTools로 재확인한 결과 1단계 로그인 응답(`flag=="4"`)은 아이디/비밀번호
  확인만 통과했다는 뜻일 뿐이고, 응답에 같이 오는 `returnUrl`(OTP 토큰 포함
  `loginCheckUsingEncryptOTP.do?...`)을 한 번 더 GET해야 실제 인증 세션이
  완성되는 2단계 SSO 구조였음(대웅더샵과 동일 패턴). 기존 코드는
  `flag=="4"`만 보고 바로 로그인 성공 처리해 실제 세션은 완성되지 않은 채
  검색이 진행되었고, 사이트가 비로그인 요청에 "로그인이 필요합니다" 알럿만
  띄우고 상품 목록 자체를 내려주지 않아 ID/PW를 정확히 입력해도 검색이
  조용히 0건이 되던 것으로 확인됨. `returnUrl` GET을 로그인 절차에 추가.
- v3.0 — 유팜몰(upharmmall.co.kr) 로그인이 실제로는 안 되고 있던 버그 수정.
  DevTools로 재확인한 결과 응답 HTML에 "mypage"/"logout" 문자열이 비로그인
  상태에도 항상 포함돼 있어(정적 "/Mypage/..." 링크들, `Logout()` 함수의
  "/Member/LogOut.aspx" 참조) `login()`의 성공 판정이 항상 True가 되어
  로그인 실패도 성공으로 오판, 실제로는 비로그인 세션으로 검색해 조용히
  0건이 되던 것으로 추정. 서버가 실제 로그인 여부에 따라 다르게 렌더링하는
  `var isLogin = "true"/"false";` 값으로 판정하도록 수정. 상품 목록 파싱도
  `tr[data-idx]`가 우측 공급사별 가격 패널과 겹치는 문제를 `#tbodyProdList
  tr[data-idx]`로 좁혀 명확화. 로그인 폼 필드도 실제 캡처와 대조해 미전송
  필드(`ex_chk`) 제거.
- v2.9 — 스마트팜(smartpharm.co.kr) 로그인이 실제로는 안 되고 있던 버그
  수정. DevTools로 재확인한 결과 로그인 폼은 `/Login/Login_Proc.asp`로
  POST되는데 `SmartPharmCrawler`는 폼이 표시되는 페이지인
  `/Login/Login.asp`에 그대로 POST하고 있었음. 사이트 홈페이지 네비게이션에
  "로그아웃" 문자열이 로그인 여부와 무관하게 항상 포함돼 있어(정적 메뉴
  항목) `login()`의 성공 판정 로직이 이를 로그인 성공으로 오판, 예외 없이
  넘어간 뒤 실제로는 비로그인 세션으로 검색해 상품이 0건으로 나오던 것으로
  추정. `LOGIN_URL`을 `Login_Proc.asp`로 수정하고, 실제 캡처된 폼 필드
  (`reURL`/`UserID`/`UserPW`)만 전송하도록 로그인 데이터도 정리.
- v2.8 — 서울약사신협(cupharm.kr) 검색 결과 상품명이 "슝猷⑥걸꼘..." 식으로
  깨져 나오던 버그 수정. v2.2에서 cp949(EUC-KR)로 확인됐던 응답 인코딩이
  이후 사이트 측에서 UTF-8로 바뀐 것으로 보이는데, 크롤러는 여전히
  cp949로 고정 디코딩하고 있어 UTF-8 응답을 cp949로 오판해 읽으면서
  한글이 깨졌음(디코딩 자체는 실패하지 않아 `UnicodeDecodeError` 없이
  조용히 깨진 문자열만 나옴). `CupharmCrawler`에 UTF-8을 우선 시도하고
  실패 시에만 cp949로 폴백하는 `_decode()` 헬퍼를 추가해 `login()`/
  `search()` 모두 이를 사용하도록 수정.
- v2.7 — 내장 사이트가 generic → 전용 크롤러로 업그레이드된 뒤에도 예전에
  저장된 config.json에서는 계속 `generic`으로 남아있던 버그 수정. "누락된
  사이트만 추가"하는 마이그레이션 로직이 `builtin_id`가 이미 있으면 손대지
  않아서, generic 시절부터 로그인 정보를 등록해 쓰던 사용자는 코드를 아무리
  새로 받아도 실제로는 계속 GenericCrawler로 동작하고 있었음. 저장된
  `crawler_type`이 최신 preset과 다르면 `crawler_type`/`login_config`/
  `selectors`/`base_url`만 최신값으로 갱신하고 크리덴셜·활성화 상태·이름은
  그대로 유지하도록 수정.
- v2.6 — 스마트팜/서울약사신협 로그인 테스트가 `UnicodeDecodeError`로 항상
  실패하던 버그 수정. 두 사이트 모두 EUC-KR 계열(cp949) 응답인데 `login()`
  안에서 encoding 지정 없이 `text()`를 호출해 UTF-8로 오판하고 있었음
  (`search()`는 이미 올바르게 처리 중이었음). 로그인 응답도 동일 encoding으로
  읽도록 수정.
- v2.5 — 내장 사이트 식별용 `builtin_id` 필드 도입. v2.1 시점엔 4개 사이트가
  `crawler_type("generic")`을 공유해 즉시 문제가 됐고, 이후 v2.2~v2.4에서
  각자 전용 크롤러로 분리되며 crawler_type 충돌 자체는 해소됐지만, 사용자가
  "사이트 관리 > 수정"에서 바꿀 수 있는 name/crawler_type으로 내장 사이트를
  식별하던 방식은 여전히 취약(수정 시 중복 추가)했음. 편집 불가능한 고정
  식별자를 도입해 `load_config()` 자동 복구, 구버전 config 마이그레이션,
  "데모 불러오기" 로그인 정보 보존 로직 세 곳의 매칭 기준을 통일.
- v2.4 — 대웅더샵/동아DAPmall을 공유 `GenericCrawler` 대신 사이트별 전용
  클래스(`DaewoongTheShopCrawler`/`DapMallCrawler`)로 분리. `crawler_type`을
  각각 `daewoongtheshop`/`dapmall`로 변경하고 `CUSTOM_CRAWLERS`에 등록. 이제
  내장 12개 사이트 전부 자기 자신만의 크롤러 클래스를 가짐. 대웅더샵의
  로그인/검색 URL·필드명은 v2.3에서 확인된 값을 그대로 사용하며, 검색 결과
  CSS 셀렉터와 동아DAPmall 전체는 여전히 미검증 placeholder.
- v2.3 — 대웅더샵(the.shop.co.kr / www.shop.co.kr) 로그인·검색 요청 형식
  일부 확인. 로그인 `POST https://www.shop.co.kr/front/front/api/auth/login`
  (필드 userId/userPwd, JSON/form-urlencoded 여부 미확인), 검색
  `GET https://the.shop.co.kr/contents/search?searchKey=all&searchVal={query}`
  (searchKey 옵션: all/상품명/제조사/보험코드/상품코드/포함성분/ATC, Next.js
  SSR 풀 페이지 HTML에 상품 리스트가 직접 렌더링됨을 확인). 상품 목록 HTML의
  정확한 CSS 셀렉터는 아직 미확인.
- v2.2 — 서울약사신협 로그인/검색 스펙 확인(사용자 제공), 전용 CupharmCrawler로
  완성. 로그인 `POST /member/login_chk.asp`(w14_user_id/w14_user_pwd 폼 POST,
  "일치하지" 문자열로 실패·"w14_user_cd" 포함 여부로 성공 판별), 검색
  `GET /order/order_goods.asp`(s_c11_med_nm 등), 결과 행 onclick의
  `fun_old_list(...)` 파라미터에서 단가/재고 추출(재고 0일 때 `<td>`가 숫자
  대신 팝업 아이콘으로 바뀌어 텍스트 파싱이 불안정하기 때문). 비밀번호 AES
  암호화 여부는 미확인 — 우선 평문 전송.
- v2.1 — 스마트팜 로그인/검색/상품목록 파싱 형식 확인, 전용 SmartPharmCrawler로
  완성. 로그인 `POST /Login/Login.asp`(UserID/UserPW 평문, 암호화 없음, 세션
  쿠키 인증), 검색 `GET /Goods/Goods_List.asp`(TopSearchKey는 EUC-KR 인코딩
  필수, TopSearch_CMP_NUM=0002 고정값), 목록 파싱은 `tr#GoodsTR` 행에서
  `a.list`(상품명)/`td.smart_nomal`(규격,제조사)/`td.smart_money2`(공급가)를
  읽고 `onclick` 속성의 `iPageGo(...Key=XXXX...)`에서 상세 페이지 Key를 추출.
- v2.0 — 검색 결과 화면에 사이트별 결과 건수 표시 추가 (0건/오류 사이트를
  검색할 때마다 바로 확인 가능). 바로팜 로그인 API 주소 변경(404) 수정,
  팜스트리트 로그인 판정 로직을 실제 AJAX/JSON 응답 기준으로 수정.
- v1.4 — 사이트 4곳 추가: 대웅더샵, 동아DAPmall, 서울약사신협, 스마트팜
  (generic 크롤러, 12사이트). 네트워크 제한으로 미검증 상태이며 로그인 URL/
  필드명/검색 셀렉터는 "사이트 관리 > 수정"에서 보정 필요.
  부수 수정: 내장 사이트 자동 복구 로직을 crawler_type 기준 → name 기준
  매칭으로 변경 (동일 crawler_type("generic")을 공유하는 사이트가 여럿일 때
  개별 누락 사이트가 복구되지 않던 문제 수정).
- v1.0 — 버전 넘버링 재시작 기준판 (8사이트 + 즐겨찾기/메모장/암호화 기능).
  전체 디버그: Generic 크롤러 검색어 URL 인코딩 누락 수정, 사이트 수정 시
  내장(builtin) 표시 소실 버그 수정, 미사용 import 제거.

### 참고: 이전 버전 이력 (재시작 이전 넘버링)
- v10.0 — 팜스트리트(보령) 크롤러 추가 (8사이트)
- v9.0  — 팜뉴트리션, 드시모네 크롤러 추가 (7사이트)
- v8.1  — 전체 디버그 (filter_cookies yarl, 우클릭 col_id 등 5건)
- v8.0  — 즐겨찾기 탭, 우클릭 메뉴, 더블클릭 상품 검색, 배송비 열 제거
- v7.x  — 메모장 탭, 로그인 테스트 개선, 새로팜 flag 타입 수정
- v6.0  — 새로팜 크롤러 추가 (5사이트)
- v5.0  — 플랫팜(NextAuth JWT) 크롤러 추가
- v4.0  — 한미몰(DWR) 크롤러 추가
- v3.0  — Windows tkinter GUI 전환
