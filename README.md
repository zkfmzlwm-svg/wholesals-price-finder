# 도매 최저가 비교 프로그램

여러 약품 도매 사이트에서 특정 제품의 최저가를 동시 검색하는 Windows 데스크탑 앱입니다.

## 현재 버전: v2.0

### 버전 정책
- 기능 추가/변경 → 정수 버전업 (예: 1.0 → 2.0)
- 사이트 추가 → 소수점 버전업 (예: 1.0 → 1.1)

## 내장 지원 사이트 (12개)
| 사이트 | 기술 스택 | 로그인 방식 |
|--------|-----------|-------------|
| 바로팜 | React SPA + REST | Token 인증 |
| 유팜몰 | ASP.NET WebForms | ViewState POST |
| 한미몰 | Spring + DWR | DWR 특수 포맷 |
| 플랫팜 | Next.js + NextAuth | JWT |
| 새로팜 | Cookie 기반 | Base64 비밀번호 |
| 팜뉴트리션 | 그누보드 PHP | 폼 POST |
| 드시모네 | Cafe24 | multipart/form-data |
| 팜스트리트 | JSP | 폼 POST |
| 대웅더샵 | Generic (미검증) | 폼 POST (placeholder) |
| 동아DAPmall | Generic (미검증) | 폼 POST (placeholder) |
| 서울약사신협 | Generic (미검증, Classic ASP 추정) | 폼 POST (placeholder) |
| 스마트팜 | Generic (미검증) | 폼 POST (placeholder) |

> 마지막 4개 사이트는 아웃바운드 네트워크가 제한된 환경에서 추가되어 실제 로그인/
> 검색 응답을 확인하지 못했습니다. 프로그램 실행 후 "사이트 관리 > 수정"에서
> 실제 로그인 URL, ID/PW input name, 검색 결과 CSS 셀렉터를 확인해 입력해야
> 정상적으로 동작합니다.

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
python wholesale_price_finder_v2.0.py
```

## exe 변환
```bash
pip install pyinstaller
pyinstaller --onefile --windowed wholesale_price_finder_v2.0.py
```

## 변경 이력
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
