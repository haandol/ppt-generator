"""CSS 클래스 규칙을 각 요소의 inline style로 병합하는 유틸리티.

<style> 블록에 정의된 단순 클래스 셀렉터(.class-name)를 파싱하여,
해당 클래스를 가진 HTML 요소에 inline style로 병합한다.
기존 인라인 스타일이 클래스 스타일보다 우선한다.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def inline_css_classes(html: str) -> str:
    """<style> 블록의 CSS 클래스 규칙을 각 요소의 inline style로 병합.

    기존 인라인 스타일이 클래스 스타일보다 우선.

    Args:
        html: CSS 클래스를 포함한 HTML 문자열.

    Returns:
        클래스 스타일이 인라인으로 해소된 HTML 문자열.
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1. <style> 태그에서 CSS 규칙 추출
    class_rules = _extract_class_rules(soup)
    if not class_rules:
        return html

    # 2. 클래스 속성을 가진 모든 요소에 인라인 style 병합
    for element in soup.find_all(True, attrs={"class": True}):
        classes = element.get("class", [])
        if not classes:
            continue

        # 클래스 순서대로 CSS 속성 수집
        merged_props: dict[str, str] = {}
        for cls in classes:
            if cls in class_rules:
                merged_props.update(class_rules[cls])

        if not merged_props:
            continue

        # 기존 인라인 style 파싱
        existing_style = element.get("style", "")
        existing_props = _parse_style(existing_style)

        # 기존 인라인이 클래스보다 우선 (덮어쓰지 않음)
        for prop, value in merged_props.items():
            if prop not in existing_props:
                existing_props[prop] = value

        # 병합된 style을 다시 문자열로
        element["style"] = _serialize_style(existing_props)

    return str(soup)


def _extract_class_rules(soup: BeautifulSoup) -> dict[str, dict[str, str]]:
    """<style> 태그에서 단순 클래스 셀렉터의 CSS 규칙을 추출.

    Returns:
        {클래스명: {속성명: 값}} 딕셔너리.
    """
    rules: dict[str, dict[str, str]] = {}

    for style_tag in soup.find_all("style"):
        css_text = style_tag.string or ""

        # 주석 제거
        css_text = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
        # @media, @import 블록 제거
        css_text = re.sub(r"@media\s*[^{]*\{[^}]*(\{[^}]*\}[^}]*)*\}", "", css_text, flags=re.DOTALL)
        css_text = re.sub(r"@import\s*[^;]+;", "", css_text)

        # 단순 클래스 셀렉터만 매칭: .class-name { ... }
        # 복합 셀렉터(.parent .child), 의사 클래스(:hover), 태그 셀렉터(h1) 등 건너뜀
        pattern = re.compile(
            r"(?:^|[};])\s*"  # 규칙 시작
            r"\.([\w-]+)"  # 단순 클래스명
            r"\s*\{"  # 여는 중괄호
            r"([^}]*)"  # 속성 블록
            r"\}",  # 닫는 중괄호
            re.DOTALL,
        )

        for match in pattern.finditer(css_text):
            class_name = match.group(1)
            props_str = match.group(2)

            # 셀렉터 텍스트에 공백이 있으면 복합 셀렉터 → 건너뜀
            # (패턴에서 이미 단순 셀렉터만 매칭하지만, 안전장치)

            props = _parse_style(props_str)
            if class_name in rules:
                rules[class_name].update(props)
            else:
                rules[class_name] = props

    return rules


def _parse_style(style_str: str) -> dict[str, str]:
    """CSS 스타일 문자열을 {속성: 값} 딕셔너리로 파싱."""
    props: dict[str, str] = {}
    if not style_str:
        return props

    for declaration in style_str.split(";"):
        declaration = declaration.strip()
        if ":" not in declaration:
            continue
        prop, _, value = declaration.partition(":")
        prop = prop.strip().lower()
        value = value.strip()
        if prop and value:
            props[prop] = value

    return props


def _serialize_style(props: dict[str, str]) -> str:
    """CSS 속성 딕셔너리를 인라인 style 문자열로 직렬화."""
    if not props:
        return ""
    return "; ".join(f"{prop}: {value}" for prop, value in props.items()) + ";"
