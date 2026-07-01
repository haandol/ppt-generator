# 테스트 가이드

## 필수 규칙

**기능 추가 또는 수정 시 반드시 테스트 코드를 함께 작성한다.**

- 새 함수/모듈 → 해당 기능을 검증하는 테스트 추가
- 기존 함수 동작 변경 → 변경된 동작을 검증하는 테스트 추가 또는 기존 테스트 수정
- 버그 수정 → 해당 버그를 재현하는 테스트를 먼저 작성하고, 수정 후 통과 확인

## pytest 설정

`pyproject.toml`에 다음 설정이 적용되어 있다:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["--strict-markers", "--strict-config", "-ra"]
```

- `--strict-markers`: 미등록 마커 사용 시 에러 (오타 방지)
- `--strict-config`: 설정 파싱 오류를 에러로 처리
- `-ra`: 실패/스킵 등 비정상 결과 요약 표시

## 테스트 구조

```
tests/
├── conftest.py               # 공통 fixture
├── test_<모듈명>.py          # 모듈별 단위 테스트
```

- 파일명: `test_<대상_모듈명>.py` (예: `test_shape_builders.py`, `test_contrast_utils.py`)
- 클래스명: `Test<기능영역>` (예: `TestTextPathPadding`, `TestHexToRelativeLuminance`)
- 메서드명: `test_<시나리오>` (예: `test_default_padding_when_none`, `test_custom_padding`)

## 작성 패턴

### 기본 구조

```python
"""<모듈명> 단위 테스트."""

from __future__ import annotations

from ppt_generator.interfaces.schemas import ...  # 필요한 스키마 임포트
from ppt_generator.tools.<모듈경로> import ...     # 테스트 대상 임포트


class Test<기능>:
    """<기능 설명>."""

    def test_<기본_동작>(self):
        # given
        ...
        # when
        result = ...
        # then
        assert ...

    def test_<경계_조건>(self):
        ...
```

### 테스트 범위 기준

하나의 기능 변경에 대해 최소한 다음을 커버한다:

1. **기본 동작 (happy path)**: 정상 입력에 대한 기대 결과
2. **기본값 / 미지정**: 옵션 필드가 None이거나 기본값일 때의 동작
3. **경계 조건**: 부분 지정, 빈 값, 극단값 등
4. **에러 케이스**: 잘못된 입력이 적절한 예외를 발생시키는지 검증

### parametrize로 반복 줄이기

동일한 로직을 다른 입력값으로 테스트할 때 `@pytest.mark.parametrize`를 사용한다:

```python
import pytest

@pytest.mark.parametrize("alignment, expected_anchor", [
    ("top", "t"),
    ("middle", "ctr"),
    ("bottom", "b"),
])
def test_vertical_alignment(alignment, expected_anchor):
    ...
```

개별 메서드로 작성해도 되지만, 입력값만 다른 반복 테스트에는 parametrize가 간결하다.

### 예외 테스트

잘못된 입력에 대한 에러 발생을 검증할 때 `pytest.raises`를 사용한다:

```python
import pytest

def test_invalid_input_raises_error():
    with pytest.raises(ValueError, match="invalid color"):
        parse_color("not-a-color")
```

### 외부 의존성 처리

- **LLM API 호출**: 이 서버는 LLM 을 직접 호출하지 않는다(생성은 MCP 클라이언트 담당). 혹시 남는 외부 API 호출이 있다면 반드시 mock 처리
- **파일시스템**: `tmp_path` fixture 사용
- **python-pptx 객체**: `Presentation()`으로 실제 객체 생성하여 테스트 (mock 불필요)

```python
from pptx import Presentation

def _make_slide():
    prs = Presentation()
    return prs.slides.add_slide(prs.slide_layouts[6])  # blank layout
```

### conftest.py 활용

여러 테스트 파일에서 반복되는 fixture/헬퍼는 `tests/conftest.py`에 정의한다. conftest.py의 fixture는 import 없이 자동 주입된다.

```python
# tests/conftest.py
import pytest
from pptx import Presentation

@pytest.fixture
def blank_slide():
    prs = Presentation()
    return prs.slides.add_slide(prs.slide_layouts[6])
```

```python
# tests/test_shape_builders.py
def test_something(blank_slide):   # conftest의 fixture가 자동 주입
    ...
```

### fixture scope

fixture는 기본적으로 `function` scope (테스트마다 새로 생성)를 사용한다. 비용이 큰 자원만 scope를 넓힌다:

- `function` (기본): 대부분의 경우. 테스트 간 격리 보장
- `module` / `session`: DB 연결, 무거운 초기화 등 생성 비용이 큰 자원에만 사용

```python
@pytest.fixture(scope="session")
def expensive_resource():
    resource = create_expensive_thing()
    yield resource
    resource.cleanup()
```

## 실행

```bash
uv run pytest                                    # 전체 테스트
uv run pytest tests/test_xxx.py -v               # 특정 파일
uv run pytest tests/test_xxx.py::TestClass -v    # 특정 클래스
uv run pytest tests/test_xxx.py::test_func -v    # 특정 함수
uv run pytest --durations=10                     # 느린 테스트 Top 10 확인
```

## 체크리스트

- [ ] 변경한 기능에 대응하는 테스트가 존재하는가?
- [ ] `uv run pytest` 전체 통과하는가?
- [ ] 외부 API 호출을 mock 처리했는가?
- [ ] 테스트가 독립적으로 실행 가능한가? (다른 테스트 순서에 의존하지 않는가)
