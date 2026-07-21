"""Line shape bbox를 방향에 맞는 두 끝점으로 변환한다."""

from __future__ import annotations


def line_endpoints(
    left: float,
    top: float,
    width: float,
    height: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """(left, top)=최소 모서리, width/height 부호=방향인 line 끝점을 반환한다."""
    right = left + abs(width)
    bottom = top + abs(height)
    start = (
        left if width >= 0 else right,
        top if height >= 0 else bottom,
    )
    end = (
        right if width >= 0 else left,
        bottom if height >= 0 else top,
    )
    return start, end
