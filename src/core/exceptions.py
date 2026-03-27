from __future__ import annotations


class AppError(Exception):
    pass


class SessionNotFoundError(AppError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session not found: {session_id}")
        self.session_id = session_id


class BundleNotFoundError(AppError):
    def __init__(self, bundle_key: str) -> None:
        super().__init__(f"Bundle not found: {bundle_key}")
        self.bundle_key = bundle_key


class TemplateLoadError(AppError):
    def __init__(self, path: str, reason: str = "") -> None:
        message = f"Failed to load template: {path}"
        if reason:
            message = f"{message} — {reason}"
        super().__init__(message)
        self.path = path


class InvalidPayloadError(AppError):
    def __init__(self, detail: str = "") -> None:
        super().__init__(f"Invalid payload: {detail}" if detail else "Invalid payload")
        self.detail = detail


class ClassificationError(AppError):
    def __init__(self, reason: str = "") -> None:
        super().__init__(
            f"Classification failed: {reason}" if reason else "Classification failed"
        )


class PreviewGenerationError(AppError):
    def __init__(self, reason: str = "") -> None:
        super().__init__(
            f"Preview generation failed: {reason}"
            if reason
            else "Preview generation failed"
        )


class BundleRegistryValidationError(AppError):
    def __init__(self, reason: str = "") -> None:
        super().__init__(
            f"Bundle registry validation failed: {reason}"
            if reason
            else "Bundle registry validation failed"
        )
        self.reason = reason
