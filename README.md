# 도매 최저가 비교 프로그램

여러 약품 도매 사이트에서 특정 제품의 최저가를 동시 검색하는 Windows 데스크탑 앱입니다.

## 현재 버전: v3.4

### 버전 정책
- 기능 추가/변경 → 정수 버전업 (예: 1.0 → 2.0)
- 사이트 추가 → 소수점 버전업 (예: 1.0 → 1.1)

## 내장 지원 사이트 (12개)
| 사이트 | 기술 스택 | 로그인 방식 |
|--------|-----------|-------------|
| 바로팜 | React SPA + REST | Token 인증 |
| 유팜몰 | ASP.NET WebForms (로그인/검색/목록 파싱 확인됨) | ViewState POST |
| 한미몰 | Spring + DWR | DWR 특수 포맷 |
| 플랫팜 | Next.js + NextAuth | JWT |
| 새로팜 | Cookie 기반 (로그인/검색/목록 파싱 확인됨) | Base64 비밀번호 + OTP 2단계 |
| 팜뉴트리션 | 그누보드 PHP (Tailwind 리뉴얼, 검색 URL 확인됨) | 폼 POST |
| 드시모네 | Cafe24 | multipart/form-data |
| 팜스트리트 | JSP | 폼 POST |
| 대웅더샵 | Next.js SSR + SSO (로그인/검색 확인됨) | JSON POST → SSO 리다이렉트 |
| 동아DAPmall | 개별 크롤러 (로그인/검색/파싱 전 항목 검증 완료) | 폼 POST (평문, userId/userPw) |
| 서울약사신협 | Classic ASP (로그인/검색 확인됨) | 폼 POST (평문, 암호화 여부 미확인) |
| 스마트팜 | Classic ASP (로그인/검색/목록 파싱 확인됨) | 폼 POST (평문, 암호화 없음) |

> 대웅더샵(`DaewoongTheShopCrawler`)/동아DAPmall(`DapMallCrawler`)은 v2.4에서
> 공유 GenericCrawler 대신 전용 크롤러 클래스로 분리됐습니다. 이제 내장 12개
> 사이트 전부 자기 자신만의 크롤러 클래스를 가지며, 로그인/검색 스펙도 모두
> DevTools 실캡쳐로 확인되어 있습니다.
>
> 대웅더샵은 로그인 도메인(www.shop.co.kr)과 서비스 도메인(the.shop.co.kr)이
> 분리된 SSO 구조입니다: `POST https://www.shop.co.kr/front/api/auth/mimsLogin`
> (JSON, 필드 identifier/password/clientIP/redirectUrl)으로 로그인하면 즉시
> 세션 쿠키를 주지 않고 `{"data": "https://mims-account.shop.co.kr/login/direct?ot=..."}`
> 형태의 SSO 리다이렉트 URL을 반환하며, 이 URL을 한 번 더 GET해야 실제
> 세션이 완성됩니다. 검색은 `GET https://the.shop.co.kr/contents/search
> ?searchKey=all&searchVal={query}`, 결과 파싱은 `div.item_result_box__Xr14g`
> 등 Next.js CSS Modules 해시 클래스를 사용합니다(사이트 재배포 시 바뀔 수
> 있음에 유의). clientIP 값이 실제 IP가 아니어도 로그인되는지는 미확인이라,
> 크롤러가 ipify로 실행 PC의 공인 IP를 조회해 채웁니다.
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
> 서울약사신협은 사용자가 직접 확인한 로그인(`POST /member/login_chk.asp`)/
> 검색(`GET /order/order_goods.asp`) 스펙으로 전용 크롤러(`CupharmCrawler`)가
> 구현되어 있습니다. 비밀번호 클라이언트측 AES 암호화 여부만 미확인 상태로,
> 우선 평문 전송합니다. 응답 페이지 인코딩이 v2.2 확인 당시엔 cp949(EUC-KR
> 상위호환)였으나 이후 사이트 측에서 UTF-8로 바뀐 것으로 보여(v2.8에서
> 검색결과 한글 깨짐으로 발견), 이제는 cp949로 고정하지 않고 UTF-8을 먼저
> 시도한 뒤 실패할 때만 cp949로 폴백합니다.

## 주요 기능
- 🔍 여러 사이트 동시 검색 및 가격 비교
- 🔒 비밀번호 AES(Fernet) 암호화 저장
- ⭐ 즐겨찾기 탭
- 📝 메모장 탭 (암호화 저장)
- 🖱️ 우클릭 컨텍스트 메뉴 (복사/즐겨찾기)
- 🔗 더블클릭 → 해당 사이트 상품 검색 페이지 오픈

## 실행 방법
```bash
pip install aiohttp beautifulsoup4 cryptography
python wholesale_price_finder_v3.4.py
```

## exe 변환
```bash
pip install pyinstaller
pyinstaller --onefile --windowed wholesale_price_finder_v3.4.py
```

## 변경 이력
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
