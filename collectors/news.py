"""
네이버 금융 뉴스 수집기

기능
- 최신 뉴스 목록 수집
- 기사 본문 수집
"""

import re
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


NEWS_URL = "https://finance.naver.com/news/mainnews.naver"
ARTICLE_TITLE_SELECTORS = (
    "#contentarea_left .article_info h3",
    "#contentarea_left .article_title",
    "h2#title_area span",
    "h2.media_end_head_headline",
)
ARTICLE_CONTENT_SELECTORS = (
    "#contentarea_left #news_read",
    "#news_read",
    "#newsct_article",
    "#dic_area",
)
ARTICLE_PRESS_SELECTORS = (
    "#contentarea_left .press_logo img",
    "#contentarea_left .press",
    ".media_end_head_top_logo img",
)
ARTICLE_PUBLISHED_AT_SELECTORS = (
    "#contentarea_left .article_info .article_date",
    "#contentarea_left .article_date",
    ".media_end_head_info_datestamp_time",
)

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
}
JAVASCRIPT_REDIRECT_PATTERN = re.compile(
    r"top\.location\.href\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def fetch_news_list(
    page: int = 1,
    timeout: int = 10,
) -> list[dict[str, Any]]:
    """
    네이버 금융 뉴스 목록을 가져온다.
    """

    params = {
        "page": page,
    }

    response = requests.get(
        NEWS_URL,
        params=params,
        timeout=timeout,
        headers=REQUEST_HEADERS,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "lxml",
    )

    news = []

    for item in soup.select("ul.newsList li"):

        a = item.select_one("dd.articleSubject a")

        if a is None:
            continue

        title = a.get_text(strip=True)

        url = "https://finance.naver.com" + a["href"]

        news.append(
            {
                "title": title,
                "url": url,
            }
        )

    return news


def fetch_news_content(
    url: str,
    timeout: int = 10,
) -> dict[str, str]:
    """네이버 금융 뉴스 기사에서 본문과 메타데이터를 가져온다.

    Args:
        url: 수집할 기사 URL
        timeout: 요청 제한 시간(초)

    Returns:
        기사 제목, 본문, 언론사, 작성시각, URL을 담은 딕셔너리

    Raises:
        ValueError: 기사 페이지에 필수 정보가 없을 때 발생한다.
    """
    response = requests.get(
        url,
        timeout=timeout,
        headers=REQUEST_HEADERS,
    )
    response.raise_for_status()

    response = _follow_javascript_redirect(response, url, timeout)

    soup = BeautifulSoup(response.text, "lxml")

    title_element = _select_first(soup, ARTICLE_TITLE_SELECTORS)
    content_element = _select_first(soup, ARTICLE_CONTENT_SELECTORS)
    press_element = _select_first(soup, ARTICLE_PRESS_SELECTORS)
    published_at_element = _select_first(soup, ARTICLE_PUBLISHED_AT_SELECTORS)

    if title_element is None or content_element is None:
        raise ValueError(f"기사의 제목 또는 본문을 찾을 수 없습니다: {url}")

    content = " ".join(content_element.stripped_strings)

    if not content:
        raise ValueError(f"기사 본문이 비어 있습니다: {url}")

    return {
        "title": title_element.get_text(" ", strip=True),
        "content": content,
        "press": _extract_press(press_element),
        "published_at": (
            published_at_element.get_text(" ", strip=True)
            if published_at_element
            else ""
        ),
        "url": url,
    }


def fetch_news(
    page: int | None = None,
    pages: int = 1,
    timeout: int = 10,
) -> list[dict[str, str]]:
    """뉴스 목록의 여러 페이지에 있는 모든 기사를 수집한다.

    목록 조회와 각 기사 본문 조회만 담당한다. 저장과 검증은 호출 계층에서
    수행한다. ``page``는 특정 한 페이지를 가져오는 기존 호출과의 호환성을 위해
    남겨 두었고, 일반적인 확장 수집은 ``pages``를 사용한다.
    """
    if pages < 1:
        raise ValueError("pages는 1 이상이어야 합니다.")

    page_numbers = [page] if page is not None else range(1, pages + 1)
    articles = [
        article
        for page_number in page_numbers
        for article in fetch_news_list(page=page_number, timeout=timeout)
    ]

    return [
        fetch_news_content(article["url"], timeout=timeout)
        for article in articles
    ]


def _select_first(soup: BeautifulSoup, selectors: tuple[str, ...]) -> Any | None:
    """후보 선택자 중 페이지에 존재하는 첫 요소를 반환한다."""
    for selector in selectors:
        element = soup.select_one(selector)
        if element is not None:
            return element
    return None


def _extract_press(element: Any | None) -> str:
    """이미지 또는 텍스트 형태의 언론사 정보를 추출한다."""
    if element is None:
        return ""
    return element.get("alt") or element.get_text(" ", strip=True)


def _follow_javascript_redirect(
    response: requests.Response,
    source_url: str,
    timeout: int,
) -> requests.Response:
    """네이버 금융의 JavaScript 기사 이동 응답을 한 번 따라간다."""
    match = JAVASCRIPT_REDIRECT_PATTERN.search(response.text)
    if match is None:
        return response

    article_url = urljoin(source_url, match.group(1))
    redirected_response = requests.get(
        article_url,
        timeout=timeout,
        headers=REQUEST_HEADERS,
    )
    redirected_response.raise_for_status()
    return redirected_response
