"""클라이언트 출력 모델의 호환 import 경로.

도메인별 모델은 output_models에 정의한다. prepare의 JSON 스키마와
ingest 검증은 여기서 재노출하는 동일한 Pydantic 모델을 사용한다.
"""

from ppt_generator.interfaces.output_models.design_doc import (
    AntiSlopGuardrailsOutput as AntiSlopGuardrailsOutput,
)
from ppt_generator.interfaces.output_models.design_doc import (
    DesignDocDraftOutput as DesignDocDraftOutput,
)
from ppt_generator.interfaces.output_models.design_doc import (
    DesignPageRequestOutput as DesignPageRequestOutput,
)
from ppt_generator.interfaces.output_models.design_doc import (
    DesignRegionOutput as DesignRegionOutput,
)
from ppt_generator.interfaces.output_models.design_doc import (
    DesignThemeOutput as DesignThemeOutput,
)
from ppt_generator.interfaces.output_models.elements import (
    ParagraphOutput as ParagraphOutput,
)
from ppt_generator.interfaces.output_models.elements import (
    ShapeOutput as ShapeOutput,
)
from ppt_generator.interfaces.output_models.elements import (
    TextBoxOutput as TextBoxOutput,
)
from ppt_generator.interfaces.output_models.elements import (
    TextRunOutput as TextRunOutput,
)
from ppt_generator.interfaces.output_models.elements import (
    _convert_paragraphs as _convert_paragraphs,
)
from ppt_generator.interfaces.output_models.elements import (
    shape_output_to_dataclass as shape_output_to_dataclass,
)
from ppt_generator.interfaces.output_models.elements import (
    textbox_output_to_dataclass as textbox_output_to_dataclass,
)
from ppt_generator.interfaces.output_models.layout import (
    DesignDocOutput as DesignDocOutput,
)
from ppt_generator.interfaces.output_models.layout import (
    GridCellAssignmentOutput as GridCellAssignmentOutput,
)
from ppt_generator.interfaces.output_models.layout import (
    GridCellOutput as GridCellOutput,
)
from ppt_generator.interfaces.output_models.layout import (
    GridLayoutOutput as GridLayoutOutput,
)
from ppt_generator.interfaces.output_models.layout import (
    LayoutNodeOutput as LayoutNodeOutput,
)
from ppt_generator.interfaces.output_models.layout import (
    _convert_flat_layout as _convert_flat_layout,
)
from ppt_generator.interfaces.output_models.layout import (
    _duplicate_values as _duplicate_values,
)
from ppt_generator.interfaces.output_models.modification import (
    BackfillDesignDocOutput as BackfillDesignDocOutput,
)
from ppt_generator.interfaces.output_models.modification import (
    BackfillElementRef as BackfillElementRef,
)
from ppt_generator.interfaces.output_models.modification import (
    BackfillNode as BackfillNode,
)
from ppt_generator.interfaces.output_models.modification import (
    ComponentModifyOutput as ComponentModifyOutput,
)
from ppt_generator.interfaces.output_models.outline import (
    ComponentHint as ComponentHint,
)
from ppt_generator.interfaces.output_models.outline import (
    OutlineOutput as OutlineOutput,
)
from ppt_generator.interfaces.output_models.outline import (
    SlideOutlineOutput as SlideOutlineOutput,
)
from ppt_generator.interfaces.output_models.review import (
    DeckReviewIssue as DeckReviewIssue,
)
from ppt_generator.interfaces.output_models.review import (
    DeckReviewOutput as DeckReviewOutput,
)
from ppt_generator.interfaces.output_models.review import (
    DesignReviewIssue as DesignReviewIssue,
)
from ppt_generator.interfaces.output_models.review import (
    DesignReviewOutput as DesignReviewOutput,
)
from ppt_generator.interfaces.output_models.script import (
    SpeakerScriptOutput as SpeakerScriptOutput,
)
from ppt_generator.interfaces.output_models.script import (
    SpeakerScriptSlideOutput as SpeakerScriptSlideOutput,
)
from ppt_generator.interfaces.output_models.slides import (
    ClosingSlideSpecOutput as ClosingSlideSpecOutput,
)
from ppt_generator.interfaces.output_models.slides import (
    ContentSlideSpecOutput as ContentSlideSpecOutput,
)
from ppt_generator.interfaces.output_models.slides import (
    OverflowContent as OverflowContent,
)
from ppt_generator.interfaces.output_models.slides import (
    SimpleSlideSpecOutput as SimpleSlideSpecOutput,
)
from ppt_generator.interfaces.output_models.slides import (
    TitleSlideSpecOutput as TitleSlideSpecOutput,
)
from ppt_generator.interfaces.output_models.slides import (
    _BaseSlideSpecOutput as _BaseSlideSpecOutput,
)
from ppt_generator.interfaces.output_models.slides import (
    _is_arrow_attachable_output_box as _is_arrow_attachable_output_box,
)
from ppt_generator.interfaces.output_models.slides import (
    _point_box_penetration_depth as _point_box_penetration_depth,
)
from ppt_generator.interfaces.output_models.slides import (
    _require_non_empty_text as _require_non_empty_text,
)
from ppt_generator.interfaces.output_models.slides import (
    _shape_output_has_text as _shape_output_has_text,
)
from ppt_generator.interfaces.output_models.slides import (
    _textbox_for_role as _textbox_for_role,
)
from ppt_generator.interfaces.output_models.slides import (
    _validate_simple_canvas as _validate_simple_canvas,
)
from ppt_generator.interfaces.output_models.slides import (
    slide_spec_output_model as slide_spec_output_model,
)
from ppt_generator.interfaces.output_models.visual_qa import (
    VisualQAContentSlideSpecOutput as VisualQAContentSlideSpecOutput,
)
from ppt_generator.interfaces.output_models.visual_qa import (
    VisualQAFixPatchOutput as VisualQAFixPatchOutput,
)
from ppt_generator.interfaces.output_models.visual_qa import (
    VisualQAIssue as VisualQAIssue,
)
from ppt_generator.interfaces.output_models.visual_qa import (
    VisualQAOutput as VisualQAOutput,
)
from ppt_generator.interfaces.output_models.visual_qa import (
    VisualQAPatchField as VisualQAPatchField,
)
from ppt_generator.interfaces.output_models.visual_qa import (
    VisualQAPatchOperation as VisualQAPatchOperation,
)
from ppt_generator.interfaces.output_models.visual_qa import (
    VisualQAShapeOutput as VisualQAShapeOutput,
)
from ppt_generator.interfaces.output_models.visual_qa import (
    VisualQASimpleSlideSpecOutput as VisualQASimpleSlideSpecOutput,
)
from ppt_generator.interfaces.output_models.visual_qa import (
    VisualQATextBoxOutput as VisualQATextBoxOutput,
)
