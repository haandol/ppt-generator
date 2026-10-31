"""슬라이드 편집 핸들러의 기존 import 경로를 보존한다."""

from ppt_generator.tools.design.handlers.component_edit import (
    _component_fingerprint as _component_fingerprint,
)
from ppt_generator.tools.design.handlers.component_edit import (
    _find_modified_element as _find_modified_element,
)
from ppt_generator.tools.design.handlers.component_edit import (
    _list_available_components as _list_available_components,
)
from ppt_generator.tools.design.handlers.component_edit import (
    handle_ingest_backfill as handle_ingest_backfill,
)
from ppt_generator.tools.design.handlers.component_edit import (
    handle_ingest_modify_component as handle_ingest_modify_component,
)
from ppt_generator.tools.design.handlers.component_edit import (
    handle_prepare_modify_component as handle_prepare_modify_component,
)
from ppt_generator.tools.design.handlers.edit_validation import (
    _raise_validation as _raise_validation,
)
from ppt_generator.tools.design.handlers.slide_edit import (
    _directives_for as _directives_for,
)
from ppt_generator.tools.design.handlers.slide_edit import (
    _handle_ingest_slide_edit_locked as _handle_ingest_slide_edit_locked,
)
from ppt_generator.tools.design.handlers.slide_edit import (
    _load_outline_for_edit as _load_outline_for_edit,
)
from ppt_generator.tools.design.handlers.slide_edit import (
    _prepare_add as _prepare_add,
)
from ppt_generator.tools.design.handlers.slide_edit import (
    _prepare_update as _prepare_update,
)
from ppt_generator.tools.design.handlers.slide_edit import (
    handle_ingest_slide_edit as handle_ingest_slide_edit,
)
from ppt_generator.tools.design.handlers.slide_edit import (
    handle_prepare_slide_edit as handle_prepare_slide_edit,
)
from ppt_generator.tools.design.handlers.slide_order import (
    handle_delete as handle_delete,
)
from ppt_generator.tools.design.handlers.slide_order import (
    handle_move as handle_move,
)
