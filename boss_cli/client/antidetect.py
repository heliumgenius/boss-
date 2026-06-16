"""Anti-detection header generation with User-Agent rotation."""
from __future__ import annotations

import random
from typing import Any

from ..constants import (
    BASE_URL,
    BOSS_CHAT_GEEK_INFO_URL,
    BOSS_CHATTED_JOB_LIST_URL,
    BOSS_EXCHANGE_CONTENT_URL,
    BOSS_EXCHANGE_REQUEST_URL,
    BOSS_FRIEND_DETAIL_URL,
    BOSS_FRIEND_LABELS_URL,
    BOSS_FRIEND_LIST_URL,
    BOSS_FRIEND_NOTE_URL,
    BOSS_GREET_REC_SORT_URL,
    BOSS_GREET_SORT_LIST_URL,
    BOSS_HISTORY_MSG_URL,
    BOSS_INTERVIEW_INVITE_URL,
    BOSS_INTERVIEW_LIST_URL,
    BOSS_JOB_OFFLINE_URL,
    BOSS_JOB_ONLINE_URL,
    BOSS_LAST_MSG_URL,
    BOSS_REMOVE_FILTER_URL,
    BOSS_SEARCH_GEEK_URL,
    BOSS_SEND_MSG_URL,
    BOSS_SESSION_ENTER_URL,
    BOSS_VIEW_GEEK_URL,
    FRIEND_ADD_URL,
    FRIEND_LIST_URL,
    GEEK_GET_JOB_URL,
    HEADERS,
    JOB_CARD_URL,
    JOB_DETAIL_URL,
    JOB_HISTORY_URL,
    JOB_SEARCH_URL,
    WEB_BOSS_CHAT_URL,
    WEB_GEEK_CHAT_URL,
    WEB_GEEK_HISTORY_URL,
    WEB_GEEK_JOB_URL,
    WEB_GEEK_RECOMMEND_URL,
)

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
]


class AntiDetect:
    """Generates browser-like request headers with User-Agent rotation."""

    def headers_for_request(self, url: str, params: dict[str, Any] | None = None, cookies: dict[str, str] | None = None) -> dict[str, str]:
        """Build browser-like headers with UA rotation and endpoint-specific Referer."""
        headers = dict(HEADERS)
        headers["User-Agent"] = random.choice(_USER_AGENTS)
        headers["X-Requested-With"] = "XMLHttpRequest"

        bst = ""
        if cookies:
            bst = cookies.get("bst", "")
        if bst:
            headers["zp_token"] = bst

        if url == JOB_SEARCH_URL:
            query = ""
            if params and params.get("query"):
                query = f"?{__import__('urllib.parse').parse.urlencode({'query': params['query']})}"
            headers["Referer"] = f"{WEB_GEEK_JOB_URL}{query}"
        elif url == GEEK_GET_JOB_URL and params and params.get("tag") == 5:
            headers["Referer"] = WEB_GEEK_RECOMMEND_URL
        elif url == GEEK_GET_JOB_URL:
            headers["Referer"] = WEB_GEEK_CHAT_URL
        elif url in (JOB_CARD_URL, JOB_DETAIL_URL):
            headers["Referer"] = WEB_GEEK_JOB_URL
        elif url == JOB_HISTORY_URL:
            headers["Referer"] = WEB_GEEK_HISTORY_URL
        elif url in (FRIEND_LIST_URL, FRIEND_ADD_URL):
            headers["Referer"] = WEB_GEEK_CHAT_URL
        elif url == BOSS_SEARCH_GEEK_URL:
            headers["Referer"] = f"{BASE_URL}/web/chat/search"
        elif url in (BOSS_VIEW_GEEK_URL, BOSS_SEND_MSG_URL):
            headers["Referer"] = WEB_BOSS_CHAT_URL
        elif url in (BOSS_FRIEND_LIST_URL, BOSS_FRIEND_DETAIL_URL, BOSS_LAST_MSG_URL,
                      BOSS_HISTORY_MSG_URL, BOSS_CHAT_GEEK_INFO_URL, BOSS_FRIEND_LABELS_URL,
                      BOSS_FRIEND_NOTE_URL, BOSS_GREET_SORT_LIST_URL, BOSS_GREET_REC_SORT_URL,
                      BOSS_CHATTED_JOB_LIST_URL, BOSS_INTERVIEW_LIST_URL,
                      BOSS_EXCHANGE_REQUEST_URL, BOSS_EXCHANGE_CONTENT_URL,
                      BOSS_INTERVIEW_INVITE_URL, BOSS_REMOVE_FILTER_URL,
                      BOSS_SESSION_ENTER_URL):
            headers["Referer"] = WEB_BOSS_CHAT_URL
        return headers
