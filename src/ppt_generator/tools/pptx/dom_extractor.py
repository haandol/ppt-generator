"""Playwright DOM 추출을 통한 HTML→PptxSlideSpec 변환 모듈.

브라우저에서 렌더링된 DOM의 getBoundingClientRect() + getComputedStyle()을
직접 추출하여 결정론적으로 PptxSlideSpec을 생성한다.
"""

from __future__ import annotations

import logging
import re

from ppt_generator.interfaces.constants import (
    SLIDES_HEIGHT_PX,
    SLIDES_WIDTH_PX,
)
from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.tools.pptx.html_parser import (
    build_single_slide_html,
    extract_head_html,
    parse_slides,
)
from ppt_generator.tools.pptx.llm_converter import validate_slide_spec

try:
    from playwright.sync_api import sync_playwright

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JavaScript: 브라우저에서 실행되어 DOM 요소 정보를 추출하는 스크립트
# ---------------------------------------------------------------------------

JS_EXTRACT_SCRIPT = """
() => {
    const SECTION = document.querySelector('section');
    if (!SECTION) return null;

    const sectionRect = SECTION.getBoundingClientRect();
    const SEC_LEFT = sectionRect.left;
    const SEC_TOP = sectionRect.top;

    // --- 유틸리티 함수 ---

    function rgbToHex(str) {
        if (!str || str === 'transparent' || str === 'rgba(0, 0, 0, 0)') return null;
        // rgba(r, g, b, a)
        let m = str.match(/rgba?\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)/);
        if (m) {
            let r = parseInt(m[1]), g = parseInt(m[2]), b = parseInt(m[3]);
            return '#' + [r, g, b].map(c => c.toString(16).padStart(2, '0')).join('');
        }
        // 이미 hex인 경우
        if (str.startsWith('#')) return str;
        return null;
    }

    function extractColorFromGradient(str) {
        // linear-gradient(160deg, #0f1b2d 0%, ...) 또는
        // linear-gradient(160deg, rgb(15, 27, 45) 0%, ...) 에서 대표색 추출
        if (!str) return null;
        if (!str.includes('gradient')) return null;
        // 전체 문자열에서 직접 색상 stop을 추출 (중첩 괄호 문제 회피)
        const stops = [];
        // hex 색상
        const hexRe = /#([0-9a-fA-F]{3,8})\\s*(\\d+)?%?/g;
        let hm;
        while ((hm = hexRe.exec(str)) !== null) {
            const hex = hm[1].length === 3
                ? '#' + hm[1][0]+hm[1][0]+hm[1][1]+hm[1][1]+hm[1][2]+hm[1][2]
                : '#' + hm[1];
            stops.push({ color: hex, pct: hm[2] ? parseInt(hm[2]) : 0 });
        }
        // rgb() 색상
        const rgbRe = /rgb\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*\\)\\s*(\\d+)?%?/g;
        let rm;
        while ((rm = rgbRe.exec(str)) !== null) {
            const hex = '#' + [rm[1],rm[2],rm[3]].map(c => parseInt(c).toString(16).padStart(2,'0')).join('');
            stops.push({ color: hex, pct: rm[4] ? parseInt(rm[4]) : 0 });
        }
        if (stops.length === 0) return null;
        // 중간 stop을 대표색으로 (보통 gradient의 시각적 중심)
        if (stops.length >= 3) return stops[Math.floor(stops.length / 2)].color;
        return stops[0].color;
    }

    function isFullScreenChild(el) {
        // section 전체를 덮는 자식인지 판별
        const r = el.getBoundingClientRect();
        return r.width >= sectionRect.width * 0.95 && r.height >= sectionRect.height * 0.95;
    }

    function extractBgColor(el) {
        // 1) computed backgroundColor (solid color)
        const cs = getComputedStyle(el);
        const solidBg = rgbToHex(cs.backgroundColor);
        if (solidBg) return solidBg;
        // 2) background-image에 gradient가 있으면 대표색 추출
        const bgImage = cs.backgroundImage;
        if (bgImage && bgImage !== 'none') {
            const gradColor = extractColorFromGradient(bgImage);
            if (gradColor) return gradColor;
        }
        // 3) inline style의 background 속성 (shorthand)
        const inlineBg = el.style.background || '';
        if (inlineBg) {
            const gradColor = extractColorFromGradient(inlineBg);
            if (gradColor) return gradColor;
            // solid color in shorthand
            const hexM = inlineBg.match(/#([0-9a-fA-F]{3,8})/);
            if (hexM) return hexM[0];
        }
        return null;
    }

    function isTransparent(color) {
        if (!color) return true;
        if (color === 'transparent' || color === 'rgba(0, 0, 0, 0)') return true;
        let m = color.match(/rgba\\(\\s*\\d+\\s*,\\s*\\d+\\s*,\\s*\\d+\\s*,\\s*([\\d.]+)\\s*\\)/);
        if (m && parseFloat(m[1]) === 0) return true;
        return false;
    }

    function pxToPt(px) {
        return Math.round(px * 0.75);
    }

    function getRelativeRect(el) {
        const r = el.getBoundingClientRect();
        return {
            left: Math.round(r.left - SEC_LEFT),
            top: Math.round(r.top - SEC_TOP),
            width: Math.round(r.width),
            height: Math.round(r.height)
        };
    }

    // --- 건너뛸 요소 판별 ---

    const SKIP_CLASSES = [
        'tech-grid', 'tech-dots', 'slide-footer', 'decorative-dots',
        'bg-pattern', 'bg-dots', 'gradient-overlay', 'noise-overlay'
    ];

    function shouldSkip(el) {
        const cs = getComputedStyle(el);
        if (cs.display === 'none') return true;
        if (cs.visibility === 'hidden') return true;
        if (cs.opacity === '0') return true;

        // Font Awesome 아이콘
        if (el.tagName === 'I') {
            const cls = el.className || '';
            if (/\\bfa[srldb]?\\b/.test(cls) || /\\bfa-/.test(cls)) return true;
        }

        // 장식 클래스
        const classes = Array.from(el.classList || []);
        for (const c of SKIP_CLASSES) {
            if (classes.includes(c)) return true;
        }

        return false;
    }

    // --- Shape 판별 클래스 ---

    const SHAPE_CLASSES = [
        'info-card', 'step-card', 'vs-panel', 'vs-badge', 'quote-box',
        'cta-box', 'arch-stage', 'pipeline-stage', 'accent-bar',
        'divider-bar', 'tag', 'token-box', 'metric-card', 'feature-card',
        'comparison-card', 'timeline-card', 'stat-card', 'benefit-card',
        'process-step', 'tech-card', 'challenge-card', 'solution-card',
        'number-badge', 'icon-box', 'label-badge', 'highlight-box',
        'card', 'badge', 'pill'
    ];

    function hasShapeClass(el) {
        const classes = Array.from(el.classList || []);
        for (const c of SHAPE_CLASSES) {
            if (classes.includes(c)) return true;
        }
        return false;
    }

    // --- 레이아웃 컨테이너 클래스 ---

    const LAYOUT_CLASSES = [
        'two-col', 'three-col', 'four-col', 'vs-container',
        'summary-grid', 'arch-flow', 'pipeline-flow', 'stats-grid',
        'metrics-grid', 'features-grid', 'cards-grid', 'grid-container',
        'flex-container', 'columns', 'row'
    ];

    function isLayoutContainer(el) {
        const cs = getComputedStyle(el);
        const classes = Array.from(el.classList || []);
        for (const c of LAYOUT_CLASSES) {
            if (classes.includes(c)) return true;
        }
        const display = cs.display;
        if ((display === 'flex' || display === 'grid' || display === 'inline-flex' || display === 'inline-grid')) {
            const bg = cs.backgroundColor;
            if (isTransparent(bg)) return true;
        }
        return false;
    }

    // --- 텍스트 요소 판별 ---

    const TEXT_TAGS = new Set(['H1','H2','H3','H4','H5','H6','P','SPAN','LABEL','A']);

    function isTextOnlyElement(el) {
        if (TEXT_TAGS.has(el.tagName)) return true;
        // div/span이면서 자식이 모두 인라인이면 텍스트 요소
        if (el.tagName === 'DIV' || el.tagName === 'SPAN') {
            const children = Array.from(el.children);
            if (children.length === 0 && el.textContent.trim()) return true;
            const allInline = children.every(c => {
                const d = getComputedStyle(c).display;
                return d === 'inline' || d === 'inline-block';
            });
            if (allInline && el.textContent.trim()) return true;
        }
        return false;
    }

    // --- Shape 판별 (배경색 기반) ---

    function isShapeElement(el) {
        if (hasShapeClass(el)) return true;
        const cs = getComputedStyle(el);
        const bg = cs.backgroundColor;
        if (isTransparent(bg)) return false;

        // 전체 화면 크기 요소는 Shape이 아니라 배경
        const r = el.getBoundingClientRect();
        if (r.width >= sectionRect.width * 0.95 && r.height >= sectionRect.height * 0.95) {
            return false;
        }

        return true;
    }

    // --- 텍스트 run 추출 ---

    function extractRuns(el) {
        const runs = [];
        function walk(node) {
            if (node.nodeType === Node.TEXT_NODE) {
                const text = node.textContent;
                if (!text.trim()) return;
                // 부모 요소의 computed style 사용
                const parent = node.parentElement;
                if (!parent) return;
                const cs = getComputedStyle(parent);
                runs.push({
                    text: text,
                    font_size_pt: pxToPt(parseFloat(cs.fontSize)),
                    color: rgbToHex(cs.color),
                    bold: parseInt(cs.fontWeight) >= 700,
                    italic: cs.fontStyle === 'italic'
                });
                return;
            }
            if (node.nodeType !== Node.ELEMENT_NODE) return;
            if (shouldSkip(node)) return;
            for (const child of node.childNodes) {
                walk(child);
            }
        }
        walk(el);
        return runs;
    }

    // --- 리스트(ul/ol) 추출 ---

    function extractList(el, baseLevel) {
        const paragraphs = [];
        const items = el.querySelectorAll(':scope > li');
        items.forEach(li => {
            const runs = extractRuns(li);
            if (runs.length > 0) {
                paragraphs.push({
                    runs: runs,
                    bullet_level: baseLevel
                });
            }
            // 중첩 리스트
            const subLists = li.querySelectorAll(':scope > ul, :scope > ol');
            subLists.forEach(sub => {
                const subParas = extractList(sub, baseLevel + 1);
                paragraphs.push(...subParas);
            });
        });
        return paragraphs;
    }

    // --- Shape 내부 복잡도 판별 ---

    function hasComplexContent(el) {
        const blockChildren = Array.from(el.children).filter(c => {
            const d = getComputedStyle(c).display;
            return d === 'block' || d === 'flex' || d === 'grid'
                || d === 'list-item' || c.tagName === 'UL' || c.tagName === 'OL';
        });
        return blockChildren.length >= 2;
    }

    // --- 메인 추출 로직 ---

    const result = {
        background_color: null,
        textboxes: [],
        shapes: []
    };

    // 1. 배경색 추출
    // (a) data-wrapper 우선
    const wrapper = SECTION.querySelector('[data-wrapper]');
    if (wrapper) {
        result.background_color = extractBgColor(wrapper);
    }
    // (b) section 자체
    if (!result.background_color) {
        result.background_color = extractBgColor(SECTION);
    }
    // (c) 전체 화면을 덮는 첫 번째 자식 div (배경 컨테이너 패턴)
    if (!result.background_color) {
        for (const child of SECTION.children) {
            if (child.tagName === 'DIV' && isFullScreenChild(child)) {
                result.background_color = extractBgColor(child);
                if (result.background_color) break;
            }
        }
    }

    // 2. DOM 순회
    function processElement(el) {
        if (shouldSkip(el)) return;

        const tag = el.tagName;

        // 배경 컨테이너 (data-wrapper 또는 전체 화면 크기 자식 div) → 자식만 처리
        if (el.hasAttribute('data-wrapper') || (el.tagName === 'DIV' && isFullScreenChild(el))) {
            for (const child of el.children) {
                processElement(child);
            }
            return;
        }

        // UL/OL → 리스트 추출
        if (tag === 'UL' || tag === 'OL') {
            const rect = getRelativeRect(el);
            if (rect.width < 5 || rect.height < 5) return;
            const paragraphs = extractList(el, 0);
            if (paragraphs.length > 0) {
                result.textboxes.push({
                    left_px: rect.left,
                    top_px: rect.top,
                    width_px: rect.width,
                    height_px: rect.height,
                    paragraphs: paragraphs
                });
            }
            return;
        }

        // Shape 요소
        if (isShapeElement(el)) {
            const rect = getRelativeRect(el);
            if (rect.width < 5 || rect.height < 5) return;

            const cs = getComputedStyle(el);
            const bgColor = rgbToHex(cs.backgroundColor);
            const borderColor = rgbToHex(cs.borderColor);
            const borderWidth = parseFloat(cs.borderWidth) || 0;
            const borderRadius = parseFloat(cs.borderRadius) || 0;

            const shapeType = borderRadius > 0 ? 'rounded_rectangle' : 'rectangle';

            if (hasComplexContent(el)) {
                // Shape(배경) + TextBox(오버레이)
                result.shapes.push({
                    left_px: rect.left,
                    top_px: rect.top,
                    width_px: rect.width,
                    height_px: rect.height,
                    shape_type: shapeType,
                    fill_color: bgColor,
                    border_color: borderWidth > 0 ? borderColor : null,
                    border_width_pt: borderWidth > 0 ? Math.round(borderWidth * 0.75) : null,
                    corner_radius_px: borderRadius > 0 ? borderRadius : null,
                    text: null,
                    text_color: null,
                    text_size_pt: null,
                    text_bold: false
                });

                // 내부 요소를 개별 처리
                for (const child of el.children) {
                    processElement(child);
                }
            } else {
                // 단순 Shape: 텍스트를 Shape 내에 포함
                const textContent = el.textContent.trim();
                const textCs = getComputedStyle(el);

                result.shapes.push({
                    left_px: rect.left,
                    top_px: rect.top,
                    width_px: rect.width,
                    height_px: rect.height,
                    shape_type: shapeType,
                    fill_color: bgColor,
                    border_color: borderWidth > 0 ? borderColor : null,
                    border_width_pt: borderWidth > 0 ? Math.round(borderWidth * 0.75) : null,
                    corner_radius_px: borderRadius > 0 ? borderRadius : null,
                    text: textContent || null,
                    text_color: rgbToHex(textCs.color),
                    text_size_pt: textContent ? pxToPt(parseFloat(textCs.fontSize)) : null,
                    text_bold: textContent ? parseInt(textCs.fontWeight) >= 700 : false
                });
            }
            return;
        }

        // 레이아웃 컨테이너 → 자식으로 재귀
        if (isLayoutContainer(el)) {
            for (const child of el.children) {
                processElement(child);
            }
            return;
        }

        // 텍스트 요소
        if (isTextOnlyElement(el)) {
            const rect = getRelativeRect(el);
            if (rect.width < 5 || rect.height < 5) return;
            const text = el.textContent.trim();
            if (!text) return;

            const runs = extractRuns(el);
            if (runs.length === 0) return;

            result.textboxes.push({
                left_px: rect.left,
                top_px: rect.top,
                width_px: rect.width,
                height_px: rect.height,
                paragraphs: [{
                    runs: runs,
                    bullet_level: -1
                }]
            });
            return;
        }

        // 기타 블록 요소 → 자식으로 재귀
        if (el.children.length > 0) {
            for (const child of el.children) {
                processElement(child);
            }
        } else {
            // 리프 요소에 텍스트가 있으면 추출
            const text = el.textContent.trim();
            if (text) {
                const rect = getRelativeRect(el);
                if (rect.width < 5 || rect.height < 5) return;
                const runs = extractRuns(el);
                if (runs.length > 0) {
                    result.textboxes.push({
                        left_px: rect.left,
                        top_px: rect.top,
                        width_px: rect.width,
                        height_px: rect.height,
                        paragraphs: [{
                            runs: runs,
                            bullet_level: -1
                        }]
                    });
                }
            }
        }
    }

    // section의 직접 자식들부터 순회 시작
    for (const child of SECTION.children) {
        processElement(child);
    }

    return result;
}
"""


# ---------------------------------------------------------------------------
# Python: JS 추출 결과 → PptxSlideSpec 변환
# ---------------------------------------------------------------------------


def _parse_extracted_data(data: dict) -> PptxSlideSpec:
    """JS 추출 결과 dict를 PptxSlideSpec으로 변환."""
    textboxes: list[PptxTextBox] = []
    for tb in data.get("textboxes", []):
        paragraphs: list[PptxParagraph] = []
        for p in tb.get("paragraphs", []):
            runs: list[PptxTextRun] = []
            for r in p.get("runs", []):
                text = r.get("text", "")
                if not text.strip():
                    continue
                runs.append(PptxTextRun(
                    text=text,
                    font_size_pt=r.get("font_size_pt"),
                    color=r.get("color"),
                    bold=r.get("bold", False),
                    italic=r.get("italic", False),
                ))
            if runs:
                paragraphs.append(PptxParagraph(
                    runs=runs,
                    bullet_level=p.get("bullet_level", -1),
                ))
        if paragraphs:
            textboxes.append(PptxTextBox(
                left_px=tb.get("left_px", 0),
                top_px=tb.get("top_px", 0),
                width_px=tb.get("width_px", 100),
                height_px=tb.get("height_px", 50),
                paragraphs=paragraphs,
            ))

    shapes: list[PptxShape] = []
    for s in data.get("shapes", []):
        shapes.append(PptxShape(
            left_px=s.get("left_px", 0),
            top_px=s.get("top_px", 0),
            width_px=s.get("width_px", 100),
            height_px=s.get("height_px", 50),
            shape_type=s.get("shape_type", "rectangle"),
            fill_color=s.get("fill_color"),
            border_color=s.get("border_color"),
            border_width_pt=s.get("border_width_pt"),
            corner_radius_px=s.get("corner_radius_px"),
            text=s.get("text"),
            text_color=s.get("text_color"),
            text_size_pt=s.get("text_size_pt"),
            text_bold=s.get("text_bold", False),
        ))

    return PptxSlideSpec(
        background_color=data.get("background_color"),
        textboxes=textboxes,
        shapes=shapes,
    )


def _deduplicate_overlapping(spec: PptxSlideSpec) -> PptxSlideSpec:
    """Shape과 TextBox가 동일 영역에 중복되는 경우 정리."""
    if not spec.shapes or not spec.textboxes:
        return spec

    # Shape 영역과 거의 겹치는 TextBox 중 Shape에 이미 text가 있으면 TextBox 제거
    filtered_textboxes: list[PptxTextBox] = []
    for tb in spec.textboxes:
        is_duplicate = False
        for s in spec.shapes:
            if s.text and _rects_overlap(
                tb.left_px, tb.top_px, tb.width_px, tb.height_px,
                s.left_px, s.top_px, s.width_px, s.height_px,
                threshold=0.8,
            ):
                # Shape이 이미 동일 텍스트를 포함하면 TextBox는 중복
                tb_text = " ".join(
                    r.text for p in tb.paragraphs for r in p.runs
                ).strip()
                if tb_text and tb_text in s.text:
                    is_duplicate = True
                    break
        if not is_duplicate:
            filtered_textboxes.append(tb)

    return PptxSlideSpec(
        background_color=spec.background_color,
        textboxes=filtered_textboxes,
        shapes=spec.shapes,
    )


def _rects_overlap(
    x1: float, y1: float, w1: float, h1: float,
    x2: float, y2: float, w2: float, h2: float,
    threshold: float = 0.8,
) -> bool:
    """두 사각형의 겹침 비율이 threshold 이상인지 판별."""
    ix = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
    iy = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
    intersection = ix * iy
    area1 = w1 * h1
    if area1 <= 0:
        return False
    return (intersection / area1) >= threshold


def extract_all_slides_via_dom(
    html: str, num_slides: int,
) -> dict[int, PptxSlideSpec | None]:
    """Playwright DOM 추출로 모든 슬라이드를 PptxSlideSpec으로 변환.

    Args:
        html: 전체 HTML 문자열 (CSS 인라이닝 전).
        num_slides: 슬라이드 개수.

    Returns:
        {슬라이드 인덱스: PptxSlideSpec | None} 딕셔너리.
        Playwright를 사용할 수 없으면 빈 dict 반환.
    """
    if not _PLAYWRIGHT_AVAILABLE:
        logger.warning("Playwright 미설치, DOM 추출 건너뜀")
        return {}

    head_html = extract_head_html(html)
    sections = parse_slides(html)
    if not sections:
        return {}

    results: dict[int, PptxSlideSpec | None] = {}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": SLIDES_WIDTH_PX, "height": SLIDES_HEIGHT_PX},
            )

            for idx, section in enumerate(sections):
                try:
                    slide_html = build_single_slide_html(head_html, section)
                    page.set_content(slide_html, wait_until="networkidle")

                    raw = page.evaluate(JS_EXTRACT_SCRIPT)
                    if raw is None:
                        logger.warning("슬라이드 %d: DOM 추출 결과 없음", idx)
                        results[idx] = None
                        continue

                    spec = _parse_extracted_data(raw)
                    spec = validate_slide_spec(spec)
                    spec = _deduplicate_overlapping(spec)
                    results[idx] = spec
                    logger.debug("슬라이드 %d: DOM 추출 완료 (TB=%d, SH=%d)",
                                 idx, len(spec.textboxes), len(spec.shapes))

                except Exception:
                    logger.exception("슬라이드 %d DOM 추출 실패", idx)
                    results[idx] = None

            browser.close()

    except Exception:
        logger.exception("Playwright 브라우저 실행 실패, DOM 추출 불가")
        return {}

    logger.info("DOM 추출 완료: %d/%d 슬라이드 성공",
                sum(1 for v in results.values() if v is not None), num_slides)
    return results
