class ApplicationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class LectureNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("LECTURE_NOT_FOUND", "Lecture not found.", 404)


class InvalidVideoLinkError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("INVALID_VIDEO_LINK", "The video link is invalid.", 403)


class VideoLinkExpiredError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("VIDEO_LINK_EXPIRED", "The video link has expired.", 410)


class UploadSessionNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("UPLOAD_SESSION_NOT_FOUND", "Upload session not found.", 404)
