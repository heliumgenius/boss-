"""Rule-based natural language → structured search parameters."""

from __future__ import annotations

import re
from typing import Any

from ..constants import CITY_CODES, DEGREE_CODES, EXP_CODES, SALARY_CODES


def _match_city(text: str) -> tuple[str | None, str]:
    for city in sorted(CITY_CODES, key=len, reverse=True):
        if city in text:
            idx = text.index(city)
            remaining = text[:idx] + text[idx + len(city):]
            return city, remaining.strip()
    return None, text


def _match_salary(text: str) -> tuple[str | None, str]:
    m = re.search(r'(\d+)\s*[kK]\s*以上', text)
    if m:
        val = int(m.group(1))
        remaining = text[:m.start()] + text[m.end():]
        for label in SALARY_CODES:
            parts = label.replace("K", "").split("-")
            if len(parts) == 2 and parts[0].isdigit() and int(parts[0]) >= val:
                return label, remaining.strip()
        return None, remaining.strip()

    m = re.search(r'(\d+)\s*[kK]\s*[-~到]\s*(\d+)\s*[kK]', text)
    if m:
        low, high = int(m.group(1)), int(m.group(2))
        remaining = text[:m.start()] + text[m.end():]
        for label in SALARY_CODES:
            if label.startswith(f"{low}-") and label.endswith(f"{high}K"):
                return label, remaining.strip()
        return None, remaining.strip()

    m = re.search(r'(\d+)\s*[kK]\s*以下', text)
    if m:
        val = int(m.group(1))
        remaining = text[:m.start()] + text[m.end():]
        for label in SALARY_CODES:
            if label == f"{val}K以下":
                return label, remaining.strip()
        return None, remaining.strip()

    return None, text


def _match_experience(text: str) -> tuple[str | None, str]:
    m = re.search(r'(\d+)\s*[-~到]\s*(\d+)\s*年', text)
    if m:
        low = int(m.group(1))
        key = f"{low}-{m.group(2)}年"
        remaining = text[:m.start()] + text[m.end():]
        for label in EXP_CODES:
            if label == key:
                return label, remaining.strip()
        return None, remaining.strip()

    m = re.search(r'(\d+)\s*年\s*以上', text)
    if m:
        val = int(m.group(1))
        remaining = text[:m.start()] + text[m.end():]
        for label in EXP_CODES:
            if label.startswith(f"{val}-"):
                return label, remaining.strip()
        return None, remaining.strip()

    m = re.search(r'(\d+)\s*年\s*以内', text)
    if m:
        val = int(m.group(1))
        remaining = text[:m.start()] + text[m.end():]
        for label in EXP_CODES:
            if label == f"{val}年以内":
                return label, remaining.strip()
        return None, remaining.strip()

    m = re.search(r'(\d+)\s*年', text)
    if m:
        val = int(m.group(1))
        remaining = text[:m.start()] + text[m.end():]
        for label in EXP_CODES:
            if label.startswith(f"{val}-"):
                return label, remaining.strip()
        return None, remaining.strip()

    return None, text


def _match_degree(text: str) -> tuple[str | None, str]:
    degrees = sorted(DEGREE_CODES, key=len, reverse=True)
    for deg in degrees:
        if deg == "不限":
            continue
        if deg in text:
            idx = text.index(deg)
            remaining = text[:idx] + text[idx + len(deg):]
            return deg, remaining.strip()
    return None, text


def parse_query(query: str) -> dict[str, Any]:
    text = query.strip()

    city, text = _match_city(text)
    salary, text = _match_salary(text)
    experience, text = _match_experience(text)
    degree, text = _match_degree(text)

    keyword = text.strip() or None

    return {
        "keyword": keyword,
        "city": city,
        "salary": salary,
        "experience": experience,
        "degree": degree,
    }
