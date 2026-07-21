from dataclasses import dataclass
import hashlib
import hmac
import time

from app.core.errors import InvalidVideoLinkError, VideoLinkExpiredError


@dataclass(frozen=True)
class SignedVideoToken:
    expires: int
    token: str


class VideoLinkSigner:
    def __init__(self, secret_key: str, ttl_seconds: int) -> None:
        self.secret_key = secret_key.encode("utf-8")
        self.ttl_seconds = ttl_seconds

    def issue(self, lecture_id: str, now: float | None = None) -> SignedVideoToken:
        issued_at = time.time() if now is None else now
        expires = int(issued_at) + self.ttl_seconds
        return SignedVideoToken(expires=expires, token=self._signature(lecture_id, expires))

    def verify(
        self,
        lecture_id: str,
        expires: int | None,
        token: str | None,
        now: float | None = None,
    ) -> None:
        if expires is None or token is None:
            raise InvalidVideoLinkError()
        current_time = time.time() if now is None else now
        if expires <= int(current_time):
            raise VideoLinkExpiredError()
        expected = self._signature(lecture_id, expires)
        if not hmac.compare_digest(token, expected):
            raise InvalidVideoLinkError()

    def _signature(self, lecture_id: str, expires: int) -> str:
        payload = f"{lecture_id}:{expires}".encode()
        return hmac.new(self.secret_key, payload, hashlib.sha256).hexdigest()
