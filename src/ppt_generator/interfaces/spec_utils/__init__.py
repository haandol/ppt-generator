"""PptxSlideSpec 파싱, 검증, 직렬화 공유 유틸리티.

하위 모듈(parser, validator, serializer)의 public API를 re-export하여
기존 import 경로 호환성을 유지한다.
"""

from ppt_generator.interfaces.spec_utils.parser import (
    parse_design_spec_json,
    parse_slide_spec,
    parse_slide_spec_json,
)
from ppt_generator.interfaces.spec_utils.serializer import (
    design_spec_to_json,
    slide_spec_to_json,
)
from ppt_generator.interfaces.spec_utils.validator import (
    validate_slide_spec,
)

__all__ = [
    "parse_slide_spec",
    "parse_slide_spec_json",
    "parse_design_spec_json",
    "slide_spec_to_json",
    "design_spec_to_json",
    "validate_slide_spec",
]
