# RA Copilot Skills

RA(Regulatory Affairs) 업무 표준 프롬프트 5종을 GitHub Copilot Agent Skill로
변환한 모음입니다. 각 폴더의 `SKILL.md`가 하나의 스킬이며, Copilot이 요청 내용을
보고 자동으로 골라 쓰거나 사용자가 직접 지정해서 호출할 수 있습니다.

## 스킬 목록

| 순번 (원본 표) | 스킬 | 폴더 | 용도 |
| --- | --- | --- | --- |
| 1 | 가이드라인/규정 검색 및 검토 | [`.github/skills/guideline-review/`](.github/skills/guideline-review/SKILL.md) | FDA·EMA·ICH·MFDS 가이드라인 근거 검토 의견 |
| 2 | 본문 요약 | [`.github/skills/ra-document-summary/`](.github/skills/ra-document-summary/SKILL.md) | 장문 기사·논문·메일의 RA 관점 요약 |
| 3 | 번역 | [`.github/skills/ra-translation/`](.github/skills/ra-translation/SKILL.md) | 외국어→한글 번역, 한글→RA 비즈니스 영어 번역·교정 |
| 7 | 텍스트 추출 | [`.github/skills/text-extraction/`](.github/skills/text-extraction/SKILL.md) | PDF 스캔·이미지·스크린샷의 텍스트/표 추출 (OCR) |
| 9 | 오류 검토 | [`.github/skills/document-error-review/`](.github/skills/document-error-review/SKILL.md) | 문서 내 오류 검토, 문서 간 Gap 검토 |

## 사용 방법

### GitHub Copilot (github.com / CLI / 코딩 에이전트)

이 저장소를 연 상태에서 평소처럼 요청하면, Copilot이 각 `SKILL.md`의
`description`을 보고 맞는 스킬을 자동으로 선택합니다.

```text
이 이슈에 대해 FDA 가이드라인 근거로 검토 의견 줘
아래 기사 RA 관점에서 요약해줘
```

### 명시적으로 지정하기

스킬명을 직접 언급하면 확실히 해당 스킬이 적용됩니다.

```text
@guideline-review 배지충전 실패 기준을 FDA/ICH 근거로 검토해줘
@ra-translation 아래 메일을 RA 비즈니스 영어로 번역·교정해줘
@text-extraction 첨부 스캔본의 표를 추출해줘
```

> VS Code Copilot Chat에서는 `.github/skills/` 아래 스킬이 자동으로
> 발견되며, 채팅에서 스킬을 참조해 사용할 수 있습니다.
>
> 다른 프로젝트에서 쓰려면 이 저장소의 `.github/skills/` 폴더를
> 대상 프로젝트의 `.github/skills/` 위치에 복사하면 됩니다.

## 공통 구조

5개 스킬 모두 원본 표의 4단 구조를 그대로 따릅니다.

1. **표준 프롬프트-질문** — 요구사항이 번호로 명시된 본 작업 프롬프트
   (번역·오류 검토처럼 유형이 2개인 업무는 질문 (1)/(2)를 모두 포함)
2. **표준 프롬프트-결과표시** — 반드시 지켜야 하는 출력 형식
3. **표준 프롬프트-검증** — 작업 후 항목별 적합/부적합을 판정하는 필수 검증 단계.
   부적합 시 수정 권고사항을 구체적으로 작성하고, 반영한 최종본을 다시 제시
4. **금지/주의 사항** — 추정 금지, Hallucination 금지 등 업무별 가드레일

따라서 어떤 스킬을 써도 결과 끝에는 항상 `## 검증 결과` 표가 함께 나옵니다.
