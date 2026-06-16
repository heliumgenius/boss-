"""API client for Boss Zhipin with rate limiting, retry, and anti-detection."""
from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

from .throttle import Throttle
from .antidetect import AntiDetect
from ..constants import (
    BASE_URL,
    BOSS_CHAT_GEEK_INFO_URL,
    BOSS_CHATTED_JOB_LIST_URL,
    BOSS_EXCHANGE_CONTENT_URL,
    BOSS_EXCHANGE_REQUEST_URL,
    BOSS_FRIEND_DETAIL_URL,
    BOSS_FRIEND_LABELS_URL,
    BOSS_FRIEND_LIST_URL,
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
    DELIVER_LIST_URL,
    FRIEND_ADD_URL,
    FRIEND_LIST_URL,
    GEEK_GET_JOB_URL,
    HEADERS,
    INTERVIEW_DATA_URL,
    JOB_CARD_URL,
    JOB_DETAIL_URL,
    JOB_HISTORY_URL,
    JOB_SEARCH_URL,
    RESUME_BASEINFO_URL,
    RESUME_EXPECT_URL,
    RESUME_STATUS_URL,
    USER_INFO_URL,
)
from ..exceptions import (
    BossApiError,
    ERROR_CODE_MAP,
    ParamError,
    RateLimitError,
    SessionExpiredError,
)

logger = logging.getLogger(__name__)


class BossClient:
    """Boss Zhipin API client with Gaussian jitter, exponential backoff, and session-stable identity.

    Anti-detection strategy:
    - Gaussian jitter delay between requests (~1s mean, sigma=0.3)
    - 5% chance of a random long pause (2-5s) to mimic reading behavior
    - Exponential backoff on HTTP 429/5xx (up to 3 retries)
    - Response cookies merged back into session jar
    - Request counter for monitoring
    """

    def __init__(
        self,
        credential: object | None = None,
        timeout: float = 30.0,
        request_delay: float = 1.0,
        max_retries: int = 3,
    ):
        self.credential = credential
        self._timeout = timeout
        self._max_retries = max_retries
        self._throttle = Throttle(request_delay)
        self._antidetect = AntiDetect()
        self._http: httpx.Client | None = None

    def _build_client(self) -> httpx.Client:
        cookies = {}
        if self.credential:
            cookies = self.credential.cookies
        return httpx.Client(
            base_url=BASE_URL,
            headers=dict(HEADERS),
            cookies=cookies,
            follow_redirects=True,
            timeout=httpx.Timeout(self._timeout),
        )

    @property
    def client(self) -> httpx.Client:
        if not self._http:
            raise RuntimeError("Client not initialized. Use 'with BossClient() as client:'")
        return self._http

    def __enter__(self) -> BossClient:
        self._http = self._build_client()
        return self

    def __exit__(self, *args: Any) -> None:
        if self._http:
            self._http.close()
            self._http = None

    # ── Rate limiting (backward-compat delegation) ──────────────────

    @property
    def _request_count(self) -> int:
        return self._throttle.request_stats["request_count"]

    @property
    def _last_request_time(self) -> float:
        return self._throttle.request_stats["last_request_time"]

    @property
    def _recent_request_times(self):
        return self._throttle._recent_request_times

    def _burst_penalty_delay(self) -> float:
        return self._throttle._burst_penalty_delay()

    @property
    def request_stats(self) -> dict[str, int | float]:
        return self._throttle.request_stats

    # ── Anti-detection (backward-compat delegation) ─────────────────

    def _headers_for_request(self, url: str, params: dict[str, Any] | None = None) -> dict[str, str]:
        cookies = dict(self.client.cookies) if self._http else {}
        return self._antidetect.headers_for_request(url, params, cookies)

    # ── Response handling ───────────────────────────────────────────

    def _merge_response_cookies(self, resp: httpx.Response) -> None:
        """Persist response Set-Cookie headers back into the session jar."""
        for name, value in resp.cookies.items():
            if value:
                self.client.cookies.set(name, value)

    def _handle_response(self, data: dict[str, Any], action: str) -> dict[str, Any]:
        """Validate API response and return zpData, raise typed exceptions."""
        code = data.get("code", -1)

        if code == 0:
            return data.get("zpData", {})

        message = data.get("message", "Unknown error")

        if code in (121, 122):
            raise BossApiError(
                f"{action}: \u8bf7\u6c42\u88ab\u5b89\u5168\u7cfb\u7edf\u62e6\u622a (code={code})."
                "\u6b64\u64cd\u4f5c\u9700\u8981\u6d4f\u89c8\u5668\u73af\u5883\u7684\u5b89\u5168\u9a8c\u8bc1\uff0cCLI \u6682\u4e0d\u652f\u6301."
                "\u8bf7\u5728 BOSS\u76f4\u8058 \u7f51\u9875\u7aef\u5b8c\u6210\u6b64\u64cd\u4f5c.",
                code=code, response=data,
            )

        exc_info = ERROR_CODE_MAP.get(code)
        if exc_info is not None:
            exc_class, msg_template = exc_info
            if exc_class is RateLimitError:
                self._throttle.start_cooldown()
            if msg_template:
                raise exc_class(msg_template.format(message=message), code=code)
            raise exc_class()

        logger.warning("Unknown API error code=%s, raw_message=%s, action=%s", code, message, action)
        raise BossApiError(f"{action}: {message} (code={code})", code=code, response=data)

    # ── Request with retry ──────────────────────────────────────────

    def _request(self, method: str, url: str, **kwargs) -> dict[str, Any]:
        """Execute HTTP request with rate-limit delay, retry, and cookie merge."""
        self._throttle.delay()
        last_exc: Exception | None = None
        params = kwargs.get("params")
        merged_headers = self._headers_for_request(url, params=params)
        request_headers = kwargs.pop("headers", None)
        if request_headers:
            merged_headers.update(request_headers)

        for attempt in range(self._max_retries):
            t0 = time.time()
            try:
                resp = self.client.request(method, url, headers=merged_headers, **kwargs)
                elapsed = time.time() - t0
                self._merge_response_cookies(resp)
                self._throttle.mark_request()

                logger.info(
                    "[#%d] %s %s -> %d (%.2fs)",
                    self._request_count, method, url[:60], resp.status_code, elapsed,
                )

                if resp.status_code in (429, 500, 502, 503, 504):
                    wait = random.uniform(0, min(30.0, 2 ** attempt))
                    logger.warning(
                        "HTTP %d from %s, retrying in %.1fs (attempt %d/%d)",
                        resp.status_code, url[:80], wait, attempt + 1, self._max_retries,
                    )
                    time.sleep(wait)
                    continue

                if resp.status_code == 404:
                    text = resp.text
                    if text.strip().startswith("{"):
                        return resp.json()
                    raise BossApiError(f"\u63a5\u53e3\u4e0d\u5b58\u5728: {url} (HTTP 404)", code=404)

                resp.raise_for_status()

                text = resp.text
                if text.startswith("<"):
                    raise BossApiError(f"Received HTML instead of JSON from {url} (possible auth redirect)")

                return resp.json()

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                elapsed = time.time() - t0
                last_exc = exc
                wait = random.uniform(0, min(30.0, 1.0 * (2 ** attempt)))
                logger.warning(
                    "[#%d] %s %s -> Network error: %s (%.2fs), retrying in %.1fs (attempt %d/%d)",
                    self._request_count + 1, method, url[:60], exc, elapsed, wait,
                    attempt + 1, self._max_retries,
                )
                time.sleep(wait)

        if last_exc:
            raise BossApiError(f"Request failed after {self._max_retries} retries: {last_exc}") from last_exc
        raise BossApiError(f"Request failed after {self._max_retries} retries")

    def _get(self, url: str, params: dict[str, Any] | None = None, action: str = "") -> dict[str, Any]:
        """GET request with response validation and rate-limit retry."""
        data = self._request("GET", url, params=params)
        try:
            result = self._handle_response(data, action)
            self._throttle.reset_cooldown()
            return result
        except RateLimitError:
            logger.info("Retrying after rate-limit cooldown...")
            data = self._request("GET", url, params=params)
            result = self._handle_response(data, action)
            self._throttle.reset_cooldown()
            return result

    # ── Job Search & Browse ─────────────────────────────────────────

    def search_jobs(
        self,
        query: str,
        city: str = "101010100",
        page: int = 1,
        page_size: int = 15,
        experience: str | None = None,
        degree: str | None = None,
        salary: str | None = None,
        industry: str | None = None,
        scale: str | None = None,
        stage: str | None = None,
        job_type: str | None = None,
    ) -> dict[str, Any]:
        """Search jobs."""
        params: dict[str, Any] = {
            "query": query,
            "city": city,
            "page": page,
            "pageSize": page_size,
        }
        if experience:
            params["experience"] = experience
        if degree:
            params["degree"] = degree
        if salary:
            params["salary"] = salary
        if industry:
            params["industry"] = industry
        if scale:
            params["scale"] = scale
        if stage:
            params["stage"] = stage
        if job_type:
            params["jobType"] = job_type
        return self._get(JOB_SEARCH_URL, params=params, action="\u641c\u7d22\u804c\u4f4d")

    def get_recommend_jobs(self, page: int = 1) -> dict[str, Any]:
        """Get personalized job recommendations."""
        data = self._get(
            GEEK_GET_JOB_URL,
            params={"page": page, "tag": 5, "isActive": "true"},
            action="\u63a8\u8350\u804c\u4f4d",
        )
        if "jobList" in data:
            return data

        card_list = data.get("cardList", [])
        return {
            "jobList": card_list,
            "hasMore": data.get("hasMore", False),
            "totalCount": data.get("totalCount", len(card_list)),
            "page": data.get("page", page),
            "startIndex": data.get("startIndex", 0),
            "type": data.get("type", 2),
            "lid": data.get("lid", ""),
        }

    def get_job_card(self, security_id: str, lid: str) -> dict[str, Any]:
        """Get job card info (hover preview)."""
        return self._get(JOB_CARD_URL, params={"securityId": security_id, "lid": lid}, action="\u804c\u4f4d\u5361\u7247")

    def get_job_detail(self, security_id: str, lid: str = "") -> dict[str, Any]:
        """Get detailed information for a specific job."""
        params: dict[str, str] = {"securityId": security_id}
        if lid:
            params["lid"] = lid
        return self._get(JOB_DETAIL_URL, params=params, action="\u804c\u4f4d\u8be6\u60c5")

    # ── Personal Center ─────────────────────────────────────────────

    def get_user_info(self) -> dict[str, Any]:
        """Get current user info (userId, name, avatar, etc.)."""
        return self._get(USER_INFO_URL, action="\u7528\u6237\u4fe1\u606f")

    def get_resume_baseinfo(self) -> dict[str, Any]:
        """Get resume basic info (full profile: name, age, degree, etc.)."""
        return self._get(RESUME_BASEINFO_URL, action="\u7b80\u5386\u57fa\u672c\u4fe1\u606f")

    def get_resume_expect(self) -> dict[str, Any]:
        """Get job expectations (desired position, salary, city)."""
        return self._get(RESUME_EXPECT_URL, action="\u6c42\u804c\u671f\u671b")

    def get_resume_status(self) -> dict[str, Any]:
        """Get resume status."""
        return self._get(RESUME_STATUS_URL, action="\u7b80\u5386\u72b6\u6001")

    def get_deliver_list(self, page: int = 1) -> dict[str, Any]:
        """Get list of jobs applied to (\u5df2\u6295\u9012)."""
        return self._get(DELIVER_LIST_URL, params={"page": page}, action="\u5df2\u6295\u9012\u5217\u8868")

    def get_interview_data(self) -> dict[str, Any]:
        """Get interview data (\u9762\u8bd5)."""
        return self._get(INTERVIEW_DATA_URL, action="\u9762\u8bd5\u6570\u636e")

    def get_job_history(self, page: int = 1) -> dict[str, Any]:
        """Get job browsing history."""
        return self._get(JOB_HISTORY_URL, params={"page": page}, action="\u6d4f\u89c8\u5386\u53f2")

    # ── Social / Chat ───────────────────────────────────────────────

    def get_friend_list(self) -> dict[str, Any]:
        """Get geek friend list (\u6c9f\u901a\u8fc7\u7684 Boss)."""
        return self._get(FRIEND_LIST_URL, action="\u597d\u53cb\u5217\u8868")

    def add_friend(self, security_id: str, lid: str = "") -> dict[str, Any]:
        """Send greeting to a Boss (\u6253\u62db\u547c / \u6295\u9012\u7b80\u5386)."""
        params: dict[str, str] = {"securityId": security_id}
        if lid:
            params["lid"] = lid
        return self._get(FRIEND_ADD_URL, params=params, action="\u6253\u62db\u547c")

    def get_geek_job(self, security_id: str) -> dict[str, Any]:
        """Get interacted job info."""
        return self._get(GEEK_GET_JOB_URL, params={"securityId": security_id}, action="\u4e92\u52a8\u804c\u4f4d")

    # ── Recruiter (Boss) Mode ────────────────────────────────────────

    def _post(self, url: str, data: dict[str, Any] | None = None, action: str = "", json_body: bool = False) -> dict[str, Any]:
        """POST request with form-encoded or JSON body, response validation, and rate-limit retry."""
        kwargs = {"json": data} if json_body else {"data": data}
        resp = self._request("POST", url, **kwargs)
        try:
            result = self._handle_response(resp, action)
            self._throttle.reset_cooldown()
            return result
        except RateLimitError:
            logger.info("Retrying after rate-limit cooldown...")
            resp = self._request("POST", url, **kwargs)
            result = self._handle_response(resp, action)
            self._throttle.reset_cooldown()
            return result

    def get_boss_chatted_jobs(self) -> list[dict[str, Any]]:
        """Get list of jobs the boss has posted (chatted job list)."""
        return self._get(BOSS_CHATTED_JOB_LIST_URL, action="\u62db\u8058\u804c\u4f4d\u5217\u8868")

    def get_boss_friend_list(self, label_id: int = 0, enc_job_id: str = "", sort: str = "", page: int = 1) -> dict[str, Any]:
        """Get boss friend list (candidates who have chatted)."""
        data: dict[str, Any] = {"labelId": label_id, "page": page}
        if enc_job_id:
            data["encJobId"] = enc_job_id
        if sort:
            data["sort"] = sort
        return self._post(BOSS_FRIEND_LIST_URL, data=data, action="\u5019\u9009\u4eba\u5217\u8868")

    def get_boss_friend_details(self, friend_ids: list[int]) -> dict[str, Any]:
        """Get detailed info for boss friends (candidates)."""
        ids_str = ",".join(str(fid) for fid in friend_ids)
        return self._post(BOSS_FRIEND_DETAIL_URL, data={"friendIds": ids_str}, action="\u5019\u9009\u4eba\u8be6\u60c5")

    def get_boss_last_messages(self, friend_ids: list[int], src: int = 0) -> list[dict[str, Any]]:
        """Get last message for each friend."""
        ids_str = ",".join(str(fid) for fid in friend_ids)
        return self._post(BOSS_LAST_MSG_URL, data={"friendIds": ids_str, "src": src}, action="\u6700\u8fd1\u6d88\u606f")

    def get_boss_chat_history(self, gid: int, count: int = 20, max_msg_id: int = 0) -> dict[str, Any]:
        """Get chat history with a specific candidate."""
        params: dict[str, Any] = {"gid": gid, "c": count, "src": 0}
        if max_msg_id:
            params["maxMsgId"] = max_msg_id
        return self._get(BOSS_HISTORY_MSG_URL, params=params, action="\u804a\u5929\u8bb0\u5f55")

    def get_boss_chat_geek_info(
        self, encrypt_geek_id: str, security_id: str, job_id: int,
    ) -> dict[str, Any]:
        """Get detailed info for a candidate in chat context."""
        return self._get(
            BOSS_CHAT_GEEK_INFO_URL,
            params={"encryptGeekId": encrypt_geek_id, "securityId": security_id, "jobId": job_id},
            action="\u5019\u9009\u4eba\u4fe1\u606f",
        )

    def get_boss_friend_labels(self) -> dict[str, Any]:
        """Get recruiter's friend labels/tags."""
        return self._get(BOSS_FRIEND_LABELS_URL, action="\u6807\u7b7e\u5217\u8868")

    def get_boss_greet_list(self, enc_job_id: str = "", page: int = 1) -> dict[str, Any]:
        """Get list of new greetings (candidates who greeted the boss)."""
        params: dict[str, Any] = {"page": page}
        if enc_job_id:
            params["encJobId"] = enc_job_id
        return self._get(BOSS_GREET_SORT_LIST_URL, params=params, action="\u65b0\u62db\u547c\u5217\u8868")

    def get_boss_greet_rec_list(self, enc_job_id: str = "", page: int = 1) -> dict[str, Any]:
        """Get recommended greeting sort list."""
        params: dict[str, Any] = {"page": page}
        if enc_job_id:
            params["encJobId"] = enc_job_id
        return self._get(BOSS_GREET_REC_SORT_URL, params=params, action="\u63a8\u8350\u62db\u547c\u6392\u5e8f")

    def get_boss_interview_list(self) -> dict[str, Any]:
        """Get boss interview list."""
        return self._get(BOSS_INTERVIEW_LIST_URL, action="\u9762\u8bd5\u5217\u8868")

    def search_geeks(
        self, query: str, city: str = "101020100", page: int = 1,
        experience: str | None = None, degree: str | None = None,
        salary: str | None = None, encrypt_job_id: str = "",
    ) -> dict[str, Any]:
        """Search candidates (geeks) as a recruiter."""
        params: dict[str, Any] = {
            "query": query, "city": city, "page": page,
        }
        if encrypt_job_id:
            params["encryptJobId"] = encrypt_job_id
        if experience:
            params["experience"] = experience
        if degree:
            params["degree"] = degree
        if salary:
            params["salary"] = salary
        return self._get(BOSS_SEARCH_GEEK_URL, params=params, action="\u641c\u7d22\u5019\u9009\u4eba")

    def get_boss_recommend_geeks(self, page: int = 1, enc_job_id: str = "") -> dict[str, Any]:
        """Get recommended candidates (new greetings sorted by recommendation)."""
        params: dict[str, Any] = {"page": page}
        if enc_job_id:
            params["encJobId"] = enc_job_id
        return self._get(BOSS_GREET_REC_SORT_URL, params=params, action="\u63a8\u8350\u5019\u9009\u4eba")

    def get_boss_view_geek(
        self, encrypt_geek_id: str, encrypt_job_id: str, security_id: str = "",
    ) -> dict[str, Any]:
        """Get full candidate resume/profile view."""
        params: dict[str, Any] = {
            "encryptGeekId": encrypt_geek_id,
            "encryptJobId": encrypt_job_id,
        }
        if security_id:
            params["securityId"] = security_id
        return self._get(BOSS_VIEW_GEEK_URL, params=params, action="\u5019\u9009\u4eba\u7b80\u5386")

    def boss_send_message(self, gid: int, content: str) -> dict[str, Any]:
        """Send a text message to a candidate as a recruiter."""
        return self._post(
            BOSS_SEND_MSG_URL,
            data={"gid": gid, "content": content},
            action="\u53d1\u9001\u6d88\u606f",
        )

    def boss_job_offline(self, encrypt_job_id: str) -> dict[str, Any]:
        """Take a job posting offline (close)."""
        return self._post(BOSS_JOB_OFFLINE_URL, data={"encryptJobId": encrypt_job_id}, action="\u5173\u95ed\u804c\u4f4d")

    def boss_job_online(self, encrypt_job_id: str) -> dict[str, Any]:
        """Bring a job posting online (reopen)."""
        return self._post(BOSS_JOB_ONLINE_URL, data={"encryptJobId": encrypt_job_id}, action="\u5f00\u542f\u804c\u4f4d")

    # ── Recruiter Chat Actions ────────────────────────────────────────

    def boss_exchange_request(self, uid: int, job_id: int, exchange_type: int) -> dict[str, Any]:
        """Request exchange with candidate.

        exchange_type: 1=phone, 2=wechat, 3=resume
        """
        return self._post(
            BOSS_EXCHANGE_REQUEST_URL,
            data={"type": exchange_type, "uid": uid, "jobId": job_id, "gid": uid},
            action="\u4ea4\u6362\u8bf7\u6c42",
        )

    def boss_get_exchange_content(self, uid: int) -> dict[str, Any]:
        """Get exchanged contact info (phone/wechat) for a candidate."""
        return self._post(
            BOSS_EXCHANGE_CONTENT_URL,
            data={"uid": uid},
            action="\u67e5\u770b\u4ea4\u6362\u5185\u5bb9",
        )

    def boss_interview_invite(
        self, encrypt_geek_id: str, encrypt_job_id: str, security_id: str,
        address: str = "", start_time: str = "", description: str = "",
    ) -> dict[str, Any]:
        """Invite candidate for an interview."""
        data: dict[str, Any] = {
            "encryptGeekId": encrypt_geek_id,
            "encryptJobId": encrypt_job_id,
            "securityId": security_id,
        }
        if address:
            data["address"] = address
        if start_time:
            data["startTime"] = start_time
        if description:
            data["description"] = description
        return self._post(BOSS_INTERVIEW_INVITE_URL, data=data, action="\u7ea6\u9762\u8bd5", json_body=True)

    def boss_mark_unsuitable(self, encrypt_geek_id: str, encrypt_job_id: str) -> dict[str, Any]:
        """Mark candidate as unsuitable."""
        return self._post(
            BOSS_REMOVE_FILTER_URL,
            data={"encryptGeekId": encrypt_geek_id, "encryptJobId": encrypt_job_id},
            action="\u6807\u8bb0\u4e0d\u5408\u9002",
        )

    def boss_session_enter(self, geek_id: str, expect_id: str, job_id: str, security_id: str) -> dict[str, Any]:
        """Enter a chat session with a candidate (required before sending messages)."""
        return self._post(
            BOSS_SESSION_ENTER_URL,
            data={"geekId": geek_id, "expectId": expect_id, "jobId": job_id, "securityId": security_id},
            action="\u8fdb\u5165\u4f1a\u8bdd",
        )
