"""로그 전송은 RAG 화면을 멈추지 않는다는 계약을 검증한다."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.event_logger import send_event


class EventLoggerTest(unittest.TestCase):
    def test_empty_collector_url_does_not_send_request(self) -> None:
        """로그 기능을 끄면 네트워크 요청 없이 False를 반환한다."""
        with patch("app.event_logger.urlopen") as mock_urlopen:
            sent = send_event(
                collector_url="",
                event_type="record_search",
                session_id="session-12345678",
            )

        self.assertFalse(sent)
        mock_urlopen.assert_not_called()

    @patch("app.event_logger.urlopen")
    def test_send_event_posts_only_supplied_aggregate_properties(
        self, mock_urlopen: MagicMock
    ) -> None:
        """이벤트는 POST /events와 호출자가 준 최소 속성만 사용한다."""
        response = MagicMock(status=202)
        mock_urlopen.return_value.__enter__.return_value = response

        sent = send_event(
            collector_url="http://localhost:8080",
            event_type="record_search",
            session_id="session-12345678",
            properties={"query_length": 8, "result_count": 3},
        )

        self.assertTrue(sent)
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:8080/events")
        self.assertIn(b'"query_length": 8', request.data)
