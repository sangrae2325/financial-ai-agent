"""뉴스 수집기 단위 테스트."""

import unittest
from unittest.mock import Mock, patch

from collectors.news import fetch_news, fetch_news_content


ARTICLE_HTML = """
<div id="contentarea_left">
  <div class="article_info">
    <h3>반도체 시장 뉴스</h3>
    <span class="article_date">2026-07-10 09:30</span>
  </div>
  <div class="press_logo"><img alt="테스트경제" /></div>
  <div id="news_read">첫 번째 문단입니다.<br/>두 번째 문단입니다.</div>
</div>
"""

NAVER_NEWS_STYLE_HTML = """
<h2 id="title_area"><span>대체 구조 기사 제목</span></h2>
<div class="media_end_head_top_logo"><img alt="대체언론사" /></div>
<span class="media_end_head_info_datestamp_time">2026-07-10 10:00</span>
<article id="dic_area">대체 구조의 기사 본문입니다.</article>
"""

JAVASCRIPT_REDIRECT_HTML = """
<script>top.location.href='https://n.news.naver.com/mnews/article/215/0001258356';</script>
"""


class NewsCollectorTest(unittest.TestCase):
    """뉴스 수집기 테스트 모음."""

    @patch("collectors.news.requests.get")
    def test_fetch_news_content_extracts_article_metadata(
        self,
        mock_get: Mock,
    ) -> None:
        """기사 HTML에서 본문 및 메타데이터를 추출한다."""
        response = Mock()
        response.text = ARTICLE_HTML
        mock_get.return_value = response

        article = fetch_news_content("https://example.com/article")

        self.assertEqual(
            article,
            {
                "title": "반도체 시장 뉴스",
                "content": "첫 번째 문단입니다. 두 번째 문단입니다.",
                "press": "테스트경제",
                "published_at": "2026-07-10 09:30",
                "url": "https://example.com/article",
            },
        )
        response.raise_for_status.assert_called_once()

    @patch("collectors.news.requests.get")
    def test_fetch_news_content_supports_alternative_article_markup(
        self,
        mock_get: Mock,
    ) -> None:
        """대체 기사 구조에서도 제목과 본문을 수집한다."""
        response = Mock()
        response.text = NAVER_NEWS_STYLE_HTML
        mock_get.return_value = response

        article = fetch_news_content("https://example.com/alternative")

        self.assertEqual(article["title"], "대체 구조 기사 제목")
        self.assertEqual(article["content"], "대체 구조의 기사 본문입니다.")
        self.assertEqual(article["press"], "대체언론사")
        self.assertEqual(article["published_at"], "2026-07-10 10:00")

    @patch("collectors.news.requests.get")
    def test_fetch_news_content_follows_javascript_redirect(
        self,
        mock_get: Mock,
    ) -> None:
        """JavaScript로 전달된 네이버 뉴스 기사 URL을 한 번 더 요청한다."""
        redirect_response = Mock()
        redirect_response.text = JAVASCRIPT_REDIRECT_HTML
        article_response = Mock()
        article_response.text = NAVER_NEWS_STYLE_HTML
        mock_get.side_effect = [redirect_response, article_response]

        article = fetch_news_content("https://finance.naver.com/news/news_read.naver")

        self.assertEqual(article["title"], "대체 구조 기사 제목")
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(
            mock_get.call_args_list[1].args[0],
            "https://n.news.naver.com/mnews/article/215/0001258356",
        )

    @patch("collectors.news.fetch_news_content")
    @patch("collectors.news.fetch_news_list")
    def test_fetch_news_collects_each_article(
        self,
        mock_list: Mock,
        mock_content: Mock,
    ) -> None:
        """목록의 각 URL에 대해 본문 수집기를 호출한다."""
        mock_list.return_value = [
            {"title": "기사 1", "url": "https://example.com/1"},
            {"title": "기사 2", "url": "https://example.com/2"},
        ]
        expected_articles = [
            {"title": "기사 1", "url": "https://example.com/1"},
            {"title": "기사 2", "url": "https://example.com/2"},
        ]
        mock_content.side_effect = expected_articles

        articles = fetch_news(page=2, timeout=5)

        self.assertEqual(articles, expected_articles)
        mock_list.assert_called_once_with(page=2, timeout=5)
        self.assertEqual(mock_content.call_count, 2)

    @patch("collectors.news.fetch_news_content")
    @patch("collectors.news.fetch_news_list")
    def test_fetch_news_collects_multiple_latest_pages(
        self,
        mock_list: Mock,
        mock_content: Mock,
    ) -> None:
        """pages 옵션은 1페이지부터 지정한 수만큼 목록을 순회한다."""
        mock_list.side_effect = [
            [{"title": "기사 1", "url": "https://example.com/1"}],
            [{"title": "기사 2", "url": "https://example.com/2"}],
            [{"title": "기사 3", "url": "https://example.com/3"}],
        ]
        mock_content.side_effect = [
            {"title": "기사 1", "url": "https://example.com/1"},
            {"title": "기사 2", "url": "https://example.com/2"},
            {"title": "기사 3", "url": "https://example.com/3"},
        ]

        articles = fetch_news(pages=3, timeout=5)

        self.assertEqual(len(articles), 3)
        self.assertEqual(
            mock_list.call_args_list,
            [
                (( ), {"page": 1, "timeout": 5}),
                (( ), {"page": 2, "timeout": 5}),
                (( ), {"page": 3, "timeout": 5}),
            ],
        )
