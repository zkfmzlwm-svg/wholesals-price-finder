# 도매 최저가 비교 프로그램

여러 약품 도매 사이트에서 특정 제품의 최저가를 동시 검색하는 Windows 데스크탑 앱입니다.

## 현재 버전: v10.0

## 내장 지원 사이트 (8개)
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
python wholesale_price_finder_v10.0.py
```

## exe 변환
```bash
pip install pyinstaller
pyinstaller --onefile --windowed wholesale_price_finder_v10.0.py
```

## 변경 이력
- v10.0 — 팜스트리트(보령) 크롤러 추가 (8사이트)
- v9.0  — 팜뉴트리션, 드시모네 크롤러 추가 (7사이트)
- v8.1  — 전체 디버그 (filter_cookies yarl, 우클릭 col_id 등 5건)
- v8.0  — 즐겨찾기 탭, 우클릭 메뉴, 더블클릭 상품 검색, 배송비 열 제거
- v7.x  — 메모장 탭, 로그인 테스트 개선, 새로팜 flag 타입 수정
- v6.0  — 새로팜 크롤러 추가 (5사이트)
- v5.0  — 플랫팜(NextAuth JWT) 크롤러 추가
- v4.0  — 한미몰(DWR) 크롤러 추가
- v3.0  — Windows tkinter GUI 전환
