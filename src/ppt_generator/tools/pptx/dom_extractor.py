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
    PptxImage,
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

    // 슬라이드 배경색 RGB (블렌딩 계산용, 배경 추출 후 설정)
    let SLIDE_BG_RGB = null;

    function parseRgba(str) {
        if (!str || str === 'transparent' || str === 'rgba(0, 0, 0, 0)') return null;
        let ma = str.match(/rgba\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*([\\d.]+)\\s*\\)/);
        if (ma) return { r: parseInt(ma[1]), g: parseInt(ma[2]), b: parseInt(ma[3]), a: parseFloat(ma[4]) };
        let m = str.match(/rgb\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*\\)/);
        if (m) return { r: parseInt(m[1]), g: parseInt(m[2]), b: parseInt(m[3]), a: 1.0 };
        return null;
    }

    function rgbToHex(str) {
        if (!str || str === 'transparent' || str === 'rgba(0, 0, 0, 0)') return null;
        const rgba = parseRgba(str);
        if (rgba) {
            if (rgba.a < 0.05) return null;  // 거의 완전 투명
            if (rgba.a < 0.15) return null;  // 매우 낮은 알파는 투명 취급 (배경 유무 무관)
            if (rgba.a < 1.0 && SLIDE_BG_RGB) {
                // 반투명: 슬라이드 배경과 알파 블렌딩
                const a = rgba.a;
                const r = Math.round(rgba.r * a + SLIDE_BG_RGB.r * (1 - a));
                const g = Math.round(rgba.g * a + SLIDE_BG_RGB.g * (1 - a));
                const b = Math.round(rgba.b * a + SLIDE_BG_RGB.b * (1 - a));
                return '#' + [r, g, b].map(c => c.toString(16).padStart(2, '0')).join('');
            }
            return '#' + [rgba.r, rgba.g, rgba.b].map(c => c.toString(16).padStart(2, '0')).join('');
        }
        if (str.startsWith('#')) return str;
        return null;
    }

    function isTransparentRaw(color) {
        // rgbToHex 블렌딩 전에 순수 투명 여부만 판별 (배경 추출용)
        if (!color) return true;
        if (color === 'transparent' || color === 'rgba(0, 0, 0, 0)') return true;
        const rgba = parseRgba(color);
        if (rgba && rgba.a < 0.05) return true;
        return false;
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
        // rgbToHex로 변환 시도 — null이면 투명
        return rgbToHex(color) === null;
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

    // --- 의미 있는 아이콘 → 유니코드 변환 (Issue 5) ---

    function getIconText(el) {
        if (el.tagName !== 'I') return null;
        const cls = el.className || '';
        if (/\\bfa-check\\b/.test(cls)) return '\\u2713 ';
        if (/\\bfa-xmark\\b|\\bfa-times\\b/.test(cls)) return '\\u2717 ';
        if (/\\bfa-arrow-right\\b/.test(cls)) return '\\u2192 ';
        if (/\\bfa-circle\\b/.test(cls)) return '\\u25CF ';
        if (/\\bfa-triangle-exclamation\\b|\\bfa-warning\\b/.test(cls)) return '\\u26A0 ';
        // 추가 아이콘 매핑 (Issue D)
        if (/\\bfa-database\\b/.test(cls)) return '\\u2630 ';
        if (/\\bfa-brain\\b/.test(cls)) return '\\uD83E\\uDDE0 ';
        if (/\\bfa-lightbulb\\b/.test(cls)) return '\\uD83D\\uDCA1 ';
        if (/\\bfa-code\\b/.test(cls)) return '<> ';
        if (/\\bfa-robot\\b/.test(cls)) return '\\uD83E\\uDD16 ';
        if (/\\bfa-ban\\b/.test(cls)) return '\\uD83D\\uDEAB ';
        if (/\\bfa-globe\\b/.test(cls)) return '\\uD83C\\uDF10 ';
        if (/\\bfa-server\\b/.test(cls)) return '\\u2630 ';
        if (/\\bfa-plug\\b/.test(cls)) return '\\uD83D\\uDD0C ';
        if (/\\bfa-cog\\b|\\bfa-gear\\b/.test(cls)) return '\\u2699 ';
        if (/\\bfa-search\\b|\\bfa-magnifying-glass\\b/.test(cls)) return '\\uD83D\\uDD0D ';
        if (/\\bfa-file\\b/.test(cls)) return '\\uD83D\\uDCC4 ';
        if (/\\bfa-link\\b/.test(cls)) return '\\uD83D\\uDD17 ';
        if (/\\bfa-star\\b/.test(cls)) return '\\u2605 ';
        if (/\\bfa-lock\\b/.test(cls)) return '\\uD83D\\uDD12 ';
        if (/\\bfa-user\\b/.test(cls)) return '\\uD83D\\uDC64 ';
        if (/\\bfa-bolt\\b/.test(cls)) return '\\u26A1 ';
        if (/\\bfa-shield\\b/.test(cls)) return '\\uD83D\\uDEE1 ';
        if (/\\bfa-book\\b/.test(cls)) return '\\uD83D\\uDCD6 ';
        if (/\\bfa-cloud\\b/.test(cls)) return '\\u2601 ';
        if (/\\bfa-circle-check\\b/.test(cls)) return '\\u2713 ';
        if (/\\bfa-scissors\\b|\\bfa-cut\\b/.test(cls)) return '\\u2702 ';
        if (/\\bfa-cubes?\\b/.test(cls)) return '\\u25A0 ';
        if (/\\bfa-download\\b/.test(cls)) return '\\u2B07 ';
        if (/\\bfa-upload\\b/.test(cls)) return '\\u2B06 ';
        if (/\\bfa-play\\b/.test(cls)) return '\\u25B6 ';
        if (/\\bfa-refresh\\b|\\bfa-rotate\\b|\\bfa-sync\\b/.test(cls)) return '\\u21BB ';
        if (/\\bfa-trash\\b/.test(cls)) return '\\uD83D\\uDDD1 ';
        if (/\\bfa-edit\\b|\\bfa-pen\\b/.test(cls)) return '\\u270F ';
        if (/\\bfa-plus\\b/.test(cls)) return '+ ';
        if (/\\bfa-minus\\b/.test(cls)) return '- ';
        if (/\\bfa-info\\b/.test(cls)) return '\\u2139 ';
        if (/\\bfa-question\\b/.test(cls)) return '? ';
        // fallback: 미등록 fa- 아이콘은 bullet으로 표시
        if (/\\bfa-\\w+/.test(cls)) return '\\u25CF ';
        return null;
    }

    function shouldSkip(el) {
        const cs = getComputedStyle(el);
        if (cs.display === 'none') return true;
        if (cs.visibility === 'hidden') return true;
        if (cs.opacity === '0') return true;

        // Font Awesome 아이콘 — 의미 있는 아이콘은 getIconText로 변환, 나머지는 스킵
        if (el.tagName === 'I') {
            const cls = el.className || '';
            if (/\\bfa[srldb]?\\b/.test(cls) || /\\bfa-/.test(cls)) {
                // getIconText가 null이면 장식 아이콘 → 스킵
                return getIconText(el) === null;
            }
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

        let isLayout = false;
        let hasExplicitLayoutClass = false;
        for (const c of LAYOUT_CLASSES) {
            if (classes.includes(c)) { isLayout = true; hasExplicitLayoutClass = true; break; }
        }
        const display = cs.display;
        if (!isLayout && (display === 'flex' || display === 'grid' || display === 'inline-flex' || display === 'inline-grid')) {
            const bg = cs.backgroundColor;
            if (isTransparent(bg)) isLayout = true;
        }
        if (!isLayout) return false;

        // 가드 1: Element 자식이 없고 텍스트만 있으면 컨테이너가 아님 (Issue 1)
        if (el.children.length === 0 && el.textContent.trim()) return false;

        // 가드 2: 명시적 LAYOUT_CLASSES가 아닌 경우,
        //         모든 자식이 텍스트 요소이면 컨테이너가 아님 (정렬용 flex)
        if (!hasExplicitLayoutClass) {
            const allTextLike = Array.from(el.children).every(c =>
                isTextOnlyElement(c) || TEXT_TAGS.has(c.tagName)
            );
            if (allTextLike && el.textContent.trim()) return false;
        }

        return true;
    }

    // --- 수직 정렬 감지 (Issue 3) ---

    function detectVerticalAlignment(el) {
        const cs = getComputedStyle(el);
        if (cs.display === 'flex' || cs.display === 'inline-flex') {
            const dir = cs.flexDirection || 'row';
            if (dir.startsWith('column')) {
                if (cs.justifyContent === 'center') return 'middle';
                if (cs.justifyContent === 'flex-end') return 'bottom';
            } else {
                if (cs.alignItems === 'center') return 'middle';
                if (cs.alignItems === 'flex-end') return 'bottom';
            }
        }
        return null;
    }

    // --- 텍스트 요소 판별 ---

    const TEXT_TAGS = new Set(['H1','H2','H3','H4','H5','H6','P','SPAN','LABEL','A']);

    function isTextOnlyElement(el) {
        if (TEXT_TAGS.has(el.tagName)) return true;
        // div/span이면서 자식이 모두 인라인이면 텍스트 요소
        if (el.tagName === 'DIV' || el.tagName === 'SPAN') {
            const children = Array.from(el.children);
            if (children.length === 0 && el.textContent.trim()) return true;
            // 텍스트 컨텐츠가 없는 자식(아이콘, BR 등)은 제외하고 판별
            const textChildren = children.filter(c => c.textContent.trim().length > 0);
            if (textChildren.length === 0 && el.textContent.trim()) return true;
            const allInline = textChildren.every(c => {
                if (c.tagName === 'BR') return true;
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

        // 최소 크기 가드: accent-bar, divider, 점 장식 등 필터링 (Issue C)
        if (r.height <= 8 || r.width <= 8) return false;
        if (r.width * r.height < 256) return false;

        return true;
    }

    // --- 텍스트가 있는 가장 깊은 요소 탐색 ---

    function findDeepestTextElement(el) {
        // 첫 번째 텍스트 노드를 포함하는 가장 깊은 Element를 반환
        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
            acceptNode: (node) => node.textContent.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT
        });
        const firstText = walker.nextNode();
        return firstText ? firstText.parentElement : null;
    }

    // --- 텍스트 run 추출 ---

    function extractRuns(el) {
        const runs = [];
        // line-height 정보를 요소 수준에서 추출
        const elCs = getComputedStyle(el);
        const elLineHeight = parseFloat(elCs.lineHeight);
        const elFontSize = parseFloat(elCs.fontSize);
        const lineHeightRatio = isNaN(elLineHeight) ? 1.2 : elLineHeight / elFontSize;

        function walk(node) {
            if (node.nodeType === Node.TEXT_NODE) {
                const text = node.textContent;
                if (!text.trim()) {
                    // Issue 2B: 인접 요소 간 공백 보존
                    if (runs.length > 0 && text.length > 0) {
                        const last = runs[runs.length - 1];
                        if (!last.text.endsWith(' ')) {
                            last.text += ' ';
                        }
                    }
                    return;
                }
                // 부모 요소의 computed style 사용
                const parent = node.parentElement;
                if (!parent) return;
                const cs = getComputedStyle(parent);
                const lh = parseFloat(cs.lineHeight);
                const fs = parseFloat(cs.fontSize);
                // Issue 4: monospace 폰트 감지
                const fontFamily = cs.fontFamily;
                const isMonospace = /monospace|Roboto\\s*Mono|Courier|Consolas/i.test(fontFamily);
                runs.push({
                    text: text,
                    font_size_pt: pxToPt(fs),
                    color: rgbToHex(cs.color),
                    bold: parseInt(cs.fontWeight) >= 700,
                    italic: cs.fontStyle === 'italic',
                    line_height_ratio: isNaN(lh) ? 1.2 : lh / fs,
                    font_family: isMonospace ? 'monospace' : null
                });
                return;
            }
            if (node.nodeType !== Node.ELEMENT_NODE) return;
            // Issue 5: 아이콘 텍스트 변환 시도 (shouldSkip 이전)
            const iconText = getIconText(node);
            if (iconText !== null) {
                const cs = getComputedStyle(node);
                runs.push({
                    text: iconText,
                    font_size_pt: pxToPt(parseFloat(cs.fontSize)),
                    color: rgbToHex(cs.color),
                    bold: false,
                    italic: false,
                    line_height_ratio: 1.2,
                    font_family: null
                });
                return;
            }
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
                const liCs = getComputedStyle(li);
                const textAlign = liCs.textAlign;
                const align = (textAlign === 'center' || textAlign === 'right') ? textAlign : 'left';
                paragraphs.push({
                    runs: runs,
                    bullet_level: baseLevel,
                    alignment: align
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

    // --- 장식 자식 요소 판별 (Issue A) ---

    function isDecorativeChild(child, parent) {
        // SHAPE_CLASSES에 명시된 요소는 항상 진짜 Shape
        if (hasShapeClass(child)) return false;

        const childRect = child.getBoundingClientRect();
        const parentRect = parent.getBoundingClientRect();
        const parentArea = parentRect.width * parentRect.height;
        const childArea = childRect.width * childRect.height;
        if (parentArea <= 0) return true;

        // 면적 비율: 부모 대비 20% 미만이면 장식
        const areaRatio = childArea / parentArea;
        if (areaRatio < 0.20) return true;

        // 높이 30px 이하: badge, accent-bar, step-number 등
        if (childRect.height <= 30) return true;

        // 유일한 자식이면 장식이 아님
        const siblings = Array.from(parent.children).filter(c => !shouldSkip(c));
        if (siblings.length <= 1) return false;

        // 내부 텍스트 없고 면적 30% 미만: 아이콘 배경 등
        const childText = child.textContent.trim();
        if (!childText && areaRatio < 0.3) return true;

        return false;
    }

    // --- 중첩 Shape 감지 ---

    function containsChildShapes(el) {
        // 직접 자식(+ flex/grid wrapper 한 단계 아래)에 Shape 요소가 있는지 감지
        for (const child of el.children) {
            if (shouldSkip(child)) continue;
            if (isShapeElement(child) && !isFullScreenChild(child)) {
                if (!isDecorativeChild(child, el)) return true;  // 장식이면 무시
            }
            // flex/grid wrapper 한 단계 아래도 확인
            const childCs = getComputedStyle(child);
            const childDisplay = childCs.display;
            if (childDisplay === 'flex' || childDisplay === 'grid' || childDisplay === 'inline-flex' || childDisplay === 'inline-grid') {
                for (const grandchild of child.children) {
                    if (shouldSkip(grandchild)) continue;
                    if (isShapeElement(grandchild) && !isFullScreenChild(grandchild)) {
                        if (!isDecorativeChild(grandchild, child)) return true;
                    }
                }
            }
        }
        return false;
    }

    // --- Shape 내부 텍스트를 paragraphs로 추출 ---

    function extractShapeParagraphs(el) {
        const paragraphs = [];

        function collectFromNode(node) {
            // Issue 2A: 텍스트 노드 직접 처리
            if (node.nodeType === Node.TEXT_NODE) {
                const text = node.textContent;
                if (!text.trim()) return;
                const parent = node.parentElement;
                if (!parent) return;
                const cs = getComputedStyle(parent);
                const lh = parseFloat(cs.lineHeight);
                const fs = parseFloat(cs.fontSize);
                const isMonospace = /monospace|Roboto\\s*Mono|Courier|Consolas/i.test(cs.fontFamily);
                paragraphs.push({
                    runs: [{ text, font_size_pt: pxToPt(fs),
                             color: rgbToHex(cs.color), bold: parseInt(cs.fontWeight)>=700,
                             italic: cs.fontStyle==='italic',
                             line_height_ratio: isNaN(lh) ? 1.2 : lh / fs,
                             font_family: isMonospace ? 'monospace' : null }],
                    bullet_level: -1, alignment: 'left'
                });
                return;
            }
            if (node.nodeType !== Node.ELEMENT_NODE) return;

            // Issue 5: 아이콘 변환
            const iconText = getIconText(node);
            if (iconText !== null) {
                const cs = getComputedStyle(node);
                paragraphs.push({
                    runs: [{ text: iconText, font_size_pt: pxToPt(parseFloat(cs.fontSize)),
                             color: rgbToHex(cs.color), bold: false, italic: false,
                             line_height_ratio: 1.2, font_family: null }],
                    bullet_level: -1, alignment: 'left'
                });
                return;
            }

            if (shouldSkip(node)) return;
            const tag = node.tagName;

            // UL/OL → 리스트 paragraphs
            if (tag === 'UL' || tag === 'OL') {
                const listParas = extractList(node, 0);
                paragraphs.push(...listParas);
                return;
            }

            // 텍스트 요소 → paragraph
            if (isTextOnlyElement(node)) {
                const text = node.textContent.trim();
                if (!text) return;
                const runs = extractRuns(node);
                if (runs.length === 0) return;
                const cs = getComputedStyle(node);
                const textAlign = cs.textAlign;
                const align = (textAlign === 'center' || textAlign === 'right') ? textAlign : 'left';
                paragraphs.push({
                    runs: runs,
                    bullet_level: -1,
                    alignment: align
                });
                return;
            }

            // 자식으로 재귀
            if (node.children.length > 0) {
                for (const child of node.childNodes) {  // Issue 2A: children → childNodes
                    collectFromNode(child);
                }
            } else {
                // 리프 요소에 텍스트가 있으면
                const text = node.textContent.trim();
                if (text) {
                    const runs = extractRuns(node);
                    if (runs.length > 0) {
                        const cs = getComputedStyle(node);
                        const textAlign = cs.textAlign;
                        const align = (textAlign === 'center' || textAlign === 'right') ? textAlign : 'left';
                        paragraphs.push({
                            runs: runs,
                            bullet_level: -1,
                            alignment: align
                        });
                    }
                }
            }
        }

        for (const child of el.childNodes) {  // Issue 2A: children → childNodes
            collectFromNode(child);
        }
        return paragraphs;
    }

    // --- Shape 내부 텍스트를 개별 textbox로 추출 (Background + Text Overlay 분리) ---

    function mapTextAlign(textAlign) {
        if (textAlign === 'center' || textAlign === 'right') return textAlign;
        return 'left';
    }

    function applyWidthPadding(rect) {
        let paddingFactor;
        if (rect.height < 35) {
            // badge/tag: 좁을수록 더 큰 패딩 (PPTX 폰트가 HTML보다 넓음)
            paddingFactor = rect.width < 120 ? 0.50 : 0.25;
        } else {
            paddingFactor = 0.10;
        }
        const extraWidth = Math.round(rect.width * paddingFactor);
        let paddedWidth = rect.width + extraWidth;
        const maxWidth = 1280 - rect.left;
        if (paddedWidth > maxWidth) paddedWidth = maxWidth;
        return paddedWidth;
    }

    function extractTextBlocksFromShape(shapeEl) {
        const textboxes = [];

        // shape 자체가 텍스트 전용 요소이면 전체를 하나의 textbox로 추출
        if (isTextOnlyElement(shapeEl)) {
            const text = shapeEl.textContent.trim();
            if (text) {
                const runs = extractRuns(shapeEl);
                if (runs.length > 0) {
                    const cs = getComputedStyle(shapeEl);
                    const rect = getRelativeRect(shapeEl);
                    const pl = parseFloat(cs.paddingLeft) || 0;
                    const pt2 = parseFloat(cs.paddingTop) || 0;
                    const pr = parseFloat(cs.paddingRight) || 0;
                    const pb = parseFloat(cs.paddingBottom) || 0;
                    const innerRect = {left: rect.left + pl, width: rect.width - pl - pr, height: rect.height - pt2 - pb};
                    textboxes.push({
                        left_px: Math.round(rect.left + pl),
                        top_px: Math.round(rect.top + pt2),
                        width_px: applyWidthPadding(innerRect),
                        height_px: Math.round(rect.height - pt2 - pb),
                        paragraphs: [{
                            runs: runs,
                            bullet_level: -1,
                            alignment: mapTextAlign(cs.textAlign),
                            line_spacing_pt: null
                        }],
                        vertical_alignment: detectVerticalAlignment(shapeEl)
                    });
                }
            }
            return textboxes;
        }

        function collectTextBlocks(node) {
            if (node.nodeType !== Node.ELEMENT_NODE) return;
            if (shouldSkip(node)) return;
            const tag = node.tagName;

            // <pre>/<code> 코드 블록 → 이미지로 캡처
            if (tag === 'PRE' || (tag === 'CODE' && node.parentElement.tagName !== 'PRE')) {
                const rect = getRelativeRect(node);
                if (rect.width < 10 || rect.height < 10) return;
                const selectorId = 'code-img-' + result.code_images.length;
                node.setAttribute('data-code-img-id', selectorId);
                result.code_images.push({
                    left_px: rect.left, top_px: rect.top,
                    width_px: rect.width, height_px: rect.height,
                    selector: '[data-code-img-id="' + selectorId + '"]'
                });
                return;
            }

            // UL/OL → 리스트 textbox
            if (tag === 'UL' || tag === 'OL') {
                const rect = getRelativeRect(node);
                if (rect.width < 5 || rect.height < 5) return;
                const paragraphs = extractList(node, 0);
                if (paragraphs.length > 0) {
                    textboxes.push({
                        left_px: Math.round(rect.left),
                        top_px: Math.round(rect.top),
                        width_px: applyWidthPadding(rect),
                        height_px: Math.round(rect.height),
                        paragraphs: paragraphs,
                        vertical_alignment: 'top'
                    });
                }
                return;
            }

            // 자식이 shape이면 processElement에서 별도 처리됨 → skip
            // 단, 텍스트만 포함하는 요소(badge/code-body 등)는 textbox로 추출
            if (isShapeElement(node) && !isDecorativeChild(node, shapeEl)) {
                if (isTextOnlyElement(node)) {
                    // 배경색이 있지만 텍스트만 포함 → textbox로 추출 (shape skip 안 함)
                } else {
                    return;
                }
            }

            // 텍스트 전용 요소 → 개별 textbox
            if (isTextOnlyElement(node) || TEXT_TAGS.has(tag)) {
                const rect = getRelativeRect(node);
                if (rect.width < 5 || rect.height < 5) return;
                const text = node.textContent.trim();
                if (!text) return;
                const runs = extractRuns(node);
                if (runs.length === 0) return;
                const cs = getComputedStyle(node);
                textboxes.push({
                    left_px: Math.round(rect.left),
                    top_px: Math.round(rect.top),
                    width_px: applyWidthPadding(rect),
                    height_px: Math.round(rect.height),
                    paragraphs: [{
                        runs: runs,
                        bullet_level: -1,
                        alignment: mapTextAlign(cs.textAlign),
                        line_spacing_pt: null
                    }],
                    vertical_alignment: 'top'
                });
                return;
            }

            // 비-shape 컨테이너 → 자식 재귀
            for (const child of node.children) {
                collectTextBlocks(child);
            }
        }

        for (const child of shapeEl.children) {
            collectTextBlocks(child);
        }

        // 자식에서 텍스트를 못 찾은 경우: shape 자체의 텍스트를 textbox로
        if (textboxes.length === 0) {
            const text = shapeEl.textContent.trim();
            if (text) {
                const runs = extractRuns(shapeEl);
                if (runs.length > 0) {
                    const cs = getComputedStyle(shapeEl);
                    const rect = getRelativeRect(shapeEl);
                    const pl = parseFloat(cs.paddingLeft) || 0;
                    const pt2 = parseFloat(cs.paddingTop) || 0;
                    const pr = parseFloat(cs.paddingRight) || 0;
                    const pb = parseFloat(cs.paddingBottom) || 0;
                    const innerRect = {left: rect.left + pl, width: rect.width - pl - pr, height: rect.height - pt2 - pb};
                    textboxes.push({
                        left_px: Math.round(rect.left + pl),
                        top_px: Math.round(rect.top + pt2),
                        width_px: applyWidthPadding(innerRect),
                        height_px: Math.round(rect.height - pt2 - pb),
                        paragraphs: [{
                            runs: runs,
                            bullet_level: -1,
                            alignment: mapTextAlign(cs.textAlign),
                            line_spacing_pt: null
                        }],
                        vertical_alignment: detectVerticalAlignment(shapeEl)
                    });
                }
            }
        }

        return textboxes;
    }

    // --- 메인 추출 로직 ---

    const result = {
        background_color: null,
        textboxes: [],
        shapes: [],
        code_images: []
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

    // 배경색을 SLIDE_BG_RGB에 설정 (반투명 요소 블렌딩용)
    if (result.background_color) {
        const hex = result.background_color.replace('#', '');
        SLIDE_BG_RGB = {
            r: parseInt(hex.substring(0, 2), 16),
            g: parseInt(hex.substring(2, 4), 16),
            b: parseInt(hex.substring(4, 6), 16),
        };
    }

    // 2. DOM 순회
    function processElement(el, parentFlexAlign) {
        // Issue 5: 의미 있는 아이콘은 shouldSkip 이전에 처리
        const iconText = getIconText(el);
        if (iconText !== null) {
            // 독립 아이콘 요소는 extractRuns 내에서 처리되므로 여기서는 스킵
            return;
        }

        if (shouldSkip(el)) return;

        const tag = el.tagName;

        // 배경 컨테이너 (data-wrapper 또는 전체 화면 크기 자식 div) → 자식만 처리
        if (el.hasAttribute('data-wrapper') || (el.tagName === 'DIV' && isFullScreenChild(el))) {
            for (const child of el.children) {
                processElement(child, parentFlexAlign);
            }
            return;
        }

        // <pre> 코드 블록 → 이미지로 캡처
        if (tag === 'PRE') {
            const rect = getRelativeRect(el);
            if (rect.width < 10 || rect.height < 10) return;
            const selectorId = 'code-img-' + result.code_images.length;
            el.setAttribute('data-code-img-id', selectorId);
            result.code_images.push({
                left_px: rect.left, top_px: rect.top,
                width_px: rect.width, height_px: rect.height,
                selector: '[data-code-img-id="' + selectorId + '"]'
            });
            return;
        }

        // UL/OL → 리스트 추출
        if (tag === 'UL' || tag === 'OL') {
            const rect = getRelativeRect(el);
            if (rect.width < 5 || rect.height < 5) return;
            const paragraphs = extractList(el, 0);
            if (paragraphs.length > 0) {
                const listCs = getComputedStyle(el);
                const lhPx = parseFloat(listCs.lineHeight);
                const lineSpacingPt = isNaN(lhPx) ? null : pxToPt(lhPx);
                result.textboxes.push({
                    left_px: rect.left,
                    top_px: rect.top,
                    width_px: rect.width,
                    height_px: rect.height,
                    paragraphs: paragraphs,
                    line_spacing_pt: lineSpacingPt,
                    vertical_alignment: null
                });
            }
            return;
        }

        // Shape 요소: 항상 background-only shape + 텍스트는 개별 textbox로 분리
        if (isShapeElement(el)) {
            const rect = getRelativeRect(el);
            if (rect.width < 10 || rect.height < 10) return;

            const cs = getComputedStyle(el);
            const bgColor = rgbToHex(cs.backgroundColor);
            const borderColor = rgbToHex(cs.borderColor);
            const borderWidth = parseFloat(cs.borderWidth) || 0;
            const borderRadiusRaw = cs.borderRadius;
            let borderRadius = 0;
            if (borderRadiusRaw && borderRadiusRaw.includes('%')) {
                borderRadius = (parseFloat(borderRadiusRaw) / 100) * Math.min(rect.width, rect.height);
            } else {
                borderRadius = parseFloat(borderRadiusRaw) || 0;
            }
            let shapeType = 'rectangle';
            if (borderRadius > 0) {
                const minDim = Math.min(rect.width, rect.height);
                shapeType = (borderRadius >= minDim * 0.4) ? 'ellipse' : 'rounded_rectangle';
            }

            // [변경] 항상 background-only shape 생성 (text/paragraphs 없음)
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
                text_bold: false,
                paragraphs: [],
                line_spacing_pt: null,
                padding_left_px: null,
                padding_right_px: null,
                padding_top_px: null,
                padding_bottom_px: null,
                vertical_alignment: detectVerticalAlignment(el)
            });

            // [변경] 텍스트 추출
            if (containsChildShapes(el)) {
                // 자식 shape이 있으면 재귀 (자식 shape도 각자 background + textbox 생성)
                for (const child of el.children) {
                    processElement(child, parentFlexAlign);
                }
            } else {
                // 자식 shape이 없으면 텍스트를 개별 textbox로 추출
                const textboxes = extractTextBlocksFromShape(el);
                for (const tb of textboxes) {
                    result.textboxes.push(tb);
                }
            }
            return;
        }

        // 레이아웃 컨테이너 → flex 정렬 전파 후 자식으로 재귀
        if (isLayoutContainer(el)) {
            const cs = getComputedStyle(el);
            let flexAlign = parentFlexAlign;
            const display = cs.display;
            if (display === 'flex' || display === 'inline-flex') {
                const flexDir = cs.flexDirection || 'row';
                if (flexDir === 'column' || flexDir === 'column-reverse') {
                    if (cs.alignItems === 'center') flexAlign = 'center';
                } else {
                    if (cs.justifyContent === 'center') flexAlign = 'center';
                }
            }
            for (const child of el.children) {
                processElement(child, flexAlign);
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

            const elCs = getComputedStyle(el);
            const textAlign = elCs.textAlign;
            let align;
            if (textAlign === 'center' || textAlign === 'right') {
                align = textAlign;
            } else if (parentFlexAlign === 'center') {
                align = 'center';
            } else {
                align = 'left';
            }

            // line-height → pt 단위 줄간격
            const lhPx = parseFloat(elCs.lineHeight);
            const lineSpacingPt = isNaN(lhPx) ? null : pxToPt(lhPx);

            result.textboxes.push({
                left_px: rect.left,
                top_px: rect.top,
                width_px: rect.height < 50 ? applyWidthPadding(rect) : rect.width,
                height_px: rect.height,
                paragraphs: [{
                    runs: runs,
                    bullet_level: -1,
                    alignment: align
                }],
                line_spacing_pt: lineSpacingPt,
                vertical_alignment: null
            });
            return;
        }

        // 기타 블록 요소 → 자식으로 재귀
        if (el.children.length > 0) {
            for (const child of el.children) {
                processElement(child, parentFlexAlign);
            }
        } else {
            // 리프 요소에 텍스트가 있으면 추출
            const text = el.textContent.trim();
            if (text) {
                const rect = getRelativeRect(el);
                if (rect.width < 5 || rect.height < 5) return;
                const runs = extractRuns(el);
                if (runs.length > 0) {
                    const leafCs = getComputedStyle(el);
                    const textAlign = leafCs.textAlign;
                    let align;
                    if (textAlign === 'center' || textAlign === 'right') {
                        align = textAlign;
                    } else if (parentFlexAlign === 'center') {
                        align = 'center';
                    } else {
                        align = 'left';
                    }
                    const lhPx = parseFloat(leafCs.lineHeight);
                    const lineSpacingPt = isNaN(lhPx) ? null : pxToPt(lhPx);
                    result.textboxes.push({
                        left_px: rect.left,
                        top_px: rect.top,
                        width_px: rect.height < 50 ? applyWidthPadding(rect) : rect.width,
                        height_px: rect.height,
                        paragraphs: [{
                            runs: runs,
                            bullet_level: -1,
                            alignment: align
                        }],
                        line_spacing_pt: lineSpacingPt,
                        vertical_alignment: null
                    });
                }
            }
        }
    }

    // section의 직접 자식들부터 순회 시작
    for (const child of SECTION.children) {
        processElement(child, null);
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
                    font_family=r.get("font_family"),
                ))
            if runs:
                paragraphs.append(PptxParagraph(
                    runs=runs,
                    bullet_level=p.get("bullet_level", -1),
                    alignment=p.get("alignment"),
                ))
        if paragraphs:
            textboxes.append(PptxTextBox(
                left_px=tb.get("left_px", 0),
                top_px=tb.get("top_px", 0),
                width_px=tb.get("width_px", 100),
                height_px=tb.get("height_px", 50),
                paragraphs=paragraphs,
                line_spacing_pt=tb.get("line_spacing_pt"),
                vertical_alignment=tb.get("vertical_alignment"),
            ))

    shapes: list[PptxShape] = []
    for s in data.get("shapes", []):
        shape_paragraphs: list[PptxParagraph] = []
        for p in s.get("paragraphs", []):
            s_runs: list[PptxTextRun] = []
            for r in p.get("runs", []):
                text = r.get("text", "")
                if not text.strip():
                    continue
                s_runs.append(PptxTextRun(
                    text=text,
                    font_size_pt=r.get("font_size_pt"),
                    color=r.get("color"),
                    bold=r.get("bold", False),
                    italic=r.get("italic", False),
                    font_family=r.get("font_family"),
                ))
            if s_runs:
                shape_paragraphs.append(PptxParagraph(
                    runs=s_runs,
                    bullet_level=p.get("bullet_level", -1),
                    alignment=p.get("alignment"),
                ))
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
            paragraphs=shape_paragraphs,
            line_spacing_pt=s.get("line_spacing_pt"),
            padding_left_px=s.get("padding_left_px"),
            padding_right_px=s.get("padding_right_px"),
            padding_top_px=s.get("padding_top_px"),
            padding_bottom_px=s.get("padding_bottom_px"),
            vertical_alignment=s.get("vertical_alignment"),
        ))

    return PptxSlideSpec(
        background_color=data.get("background_color"),
        textboxes=textboxes,
        shapes=shapes,
    )


def _deduplicate_overlapping(spec: PptxSlideSpec) -> PptxSlideSpec:
    """동일 위치에 동일 텍스트를 가진 TextBox 중복 제거."""
    if not spec.textboxes:
        return spec

    filtered: list[PptxTextBox] = []
    for tb in spec.textboxes:
        tb_text = " ".join(
            r.text for p in tb.paragraphs for r in p.runs
        ).strip()
        is_dup = False
        for other in filtered:
            other_text = " ".join(
                r.text for p in other.paragraphs for r in p.runs
            ).strip()
            if tb_text and other_text and tb_text == other_text:
                if _rects_overlap(
                    tb.left_px, tb.top_px, tb.width_px, tb.height_px,
                    other.left_px, other.top_px, other.width_px, other.height_px,
                    threshold=0.7,
                ):
                    is_dup = True
                    break
        if not is_dup:
            filtered.append(tb)

    return PptxSlideSpec(
        background_color=spec.background_color,
        textboxes=filtered,
        shapes=spec.shapes,
        images=spec.images,
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

                    # 코드 블록 스크린샷 캡처
                    code_images: list[PptxImage] = []
                    for ci in raw.get("code_images", []):
                        selector = ci.get("selector", "")
                        if not selector:
                            continue
                        try:
                            el = page.query_selector(selector)
                            if el:
                                png_bytes = el.screenshot(type="png")
                                code_images.append(PptxImage(
                                    left_px=ci["left_px"],
                                    top_px=ci["top_px"],
                                    width_px=ci["width_px"],
                                    height_px=ci["height_px"],
                                    image_bytes=png_bytes,
                                ))
                        except Exception:
                            logger.warning("슬라이드 %d: 코드 블록 스크린샷 실패", idx)

                    spec = _parse_extracted_data(raw)
                    if code_images:
                        spec = PptxSlideSpec(
                            background_color=spec.background_color,
                            textboxes=spec.textboxes,
                            shapes=spec.shapes,
                            images=code_images,
                        )
                    spec = validate_slide_spec(spec)
                    spec = _deduplicate_overlapping(spec)
                    results[idx] = spec
                    logger.debug("슬라이드 %d: DOM 추출 완료 (TB=%d, SH=%d, IMG=%d)",
                                 idx, len(spec.textboxes), len(spec.shapes),
                                 len(spec.images))

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
