"""컨테이너의 지연 생성과 인스턴스 격리 계약."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from ppt_generator.di import container


@pytest.mark.parametrize(
    ("property_name", "class_name"),
    [
        ("outline_service", "OutlineService"),
        ("export_service", "ExportService"),
        ("slides_service", "SlidesService"),
        ("project_service", "ProjectService"),
        ("import_service", "ImportService"),
        ("design_service", "DesignService"),
        ("review_service", "DesignReviewService"),
        ("visual_qa_service", "VisualQAService"),
        ("script_service", "SpeakerScriptService"),
    ],
)
def test_services_are_lazy_reused_and_isolated(
    property_name: str, class_name: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    factory = Mock(side_effect=[object(), object()])
    monkeypatch.setattr(container, class_name, factory)
    first = container.DIContainer(project_root=tmp_path)
    second = container.DIContainer(project_root=tmp_path)
    factory.assert_not_called()

    service = getattr(first, property_name)
    assert getattr(first, property_name) is service
    factory.assert_called_once_with()
    assert getattr(second, property_name) is not service
    assert factory.call_count == 2
