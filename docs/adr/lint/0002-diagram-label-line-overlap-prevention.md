# Diagram Label-Line Overlap Prevention

Date: 2026-04-15

## Status

Accepted (2026-04-15)
## Context

다이어그램(arch_diagram, pipeline, process_flow)에서 화살표/선(line shape) 위에 텍스트 레이블이 겹쳐 렌더링되는 문제가 빈번하게 발생한다. 스크린샷 예시(시퀀스 다이어그램)에서 확인되듯이, 화살표 위에 놓인 텍스트가 선과 겹쳐 가독성이 크게 저하된다.

현재 프롬프트에는:
- `overlap` 이슈 타입이 존재하지만, 선(line)과 텍스트의 겹침은 명시적으로 다루지 않음
- Design spec 생성 프롬프트(`design_system_content.prompt.md`)의 constraint 2에서 "Line/arrow shapes may overlap block shapes"라고 허용하면서, 텍스트 레이블과의 겹침도 묵시적으로 허용하는 결과를 초래

추가 요청: 다이어그램의 선 위/아래 레이블 텍스트 크기를 12pt 또는 14pt로 고정한다.

## Decision

### 1. Design spec 생성 프롬프트 보강 (`design_system_content.prompt.md`)

Constraint 2의 line/arrow overlap 규칙을 명확히 수정:
- **기존**: "Line/arrow shapes may overlap block shapes. Textbox labels must NOT overlap shapes — put labels in the shape's paragraphs."
- **변경**: "Line/arrow shapes may overlap block shapes (pass through/behind). **Text labels placed near arrows (step labels, flow descriptions) must NOT visually overlap any line/arrow shape.** Place labels above or below the arrow with a minimum 4px vertical gap from the line's vertical center. If space is tight, offset the label horizontally to a clear area."

다이어그램 레이블 폰트 크기 규칙 추가:
- 다이어그램의 선 위/아래에 위치하는 flow label 텍스트는 12pt 또는 14pt로 고정
- `<typography_rules>`에 "Diagram flow label (text near arrows): 12~14pt" 항목 추가

### 2. Visual QA 분석 프롬프트 보강 (`visual_qa_analysis.prompt.md`)

`<issue_types>` 테이블에 새 이슈 타입 추가:
- `label_line_overlap`: 텍스트 레이블이 화살표/선과 시각적으로 겹쳐 가독성이 저하되는 경우

`<guidelines>`에 감지 규칙 추가:
- line shape(shape_type=="line")의 경로와 인접 textbox/shape text의 bounding box가 겹치는지 확인
- 수평 화살표: 레이블의 top_px ~ top_px+height_px 범위가 화살표의 top_px를 포함하면 겹침
- 수직 화살표: 레이블의 left_px ~ left_px+width_px 범위가 화살표의 left_px를 포함하면 겹침

### 3. Visual QA 수정 프롬프트 보강 (`visual_qa_fix.prompt.md`)

`<fix_strategies>`에 수정 전략 추가:
- `label_line_overlap`: 레이블을 화살표 위 또는 아래로 이동하여 최소 4px 간격 확보. 레이블 top_px를 arrow.top_px - label.height_px - 4 (위) 또는 arrow.top_px + 4 (아래)로 조정.

## Technical Details

변경 대상 파일:
- `src/ppt_generator/interfaces/prompts/design_system_content.prompt.md`
- `src/ppt_generator/interfaces/prompts/visual_qa_analysis.prompt.md`
- `src/ppt_generator/interfaces/prompts/visual_qa_fix.prompt.md`

## Consequences

- 다이어그램 생성 시 LLM이 선과 레이블 겹침을 사전에 회피
- Visual QA에서 겹침이 발생한 경우 자동 감지 및 수정
- 다이어그램 레이블 폰트 크기가 12~14pt로 일관되게 유지
