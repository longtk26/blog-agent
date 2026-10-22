from fastapi import HTTPException
from http import HTTPStatus
from typing import Any

from .error_codes import ErrorCode


class BaseException(HTTPException):
    def __init__(self, status_code: int, detail: Any, code: ErrorCode | str = ErrorCode.HTTP_ERROR):
        super().__init__(status_code=status_code, detail=detail)
        self.code = str(code)

class NotFoundException(BaseException):
    def __init__(self, detail: Any = "Resource not found", code: ErrorCode | str = ErrorCode.NOT_FOUND):
        super().__init__(status_code=HTTPStatus.NOT_FOUND, detail=detail, code=code)

class BadRequestException(BaseException):
    def __init__(self, detail: Any = "Bad request", code: ErrorCode | str = ErrorCode.BAD_REQUEST):
        super().__init__(status_code=HTTPStatus.BAD_REQUEST, detail=detail, code=code)

class UnauthorizedException(BaseException):
    def __init__(self, detail: Any = "Unauthorized", code: ErrorCode | str = ErrorCode.UNAUTHORIZED):
        super().__init__(status_code=HTTPStatus.UNAUTHORIZED, detail=detail, code=code)

class ForbiddenException(BaseException):
    def __init__(self, detail: Any = "Forbidden", code: ErrorCode | str = ErrorCode.FORBIDDEN):
        super().__init__(status_code=HTTPStatus.FORBIDDEN, detail=detail, code=code)

class ConflictException(BaseException):
    def __init__(self, detail: Any = "Conflict", code: ErrorCode | str = ErrorCode.CONFLICT):
        super().__init__(status_code=HTTPStatus.CONFLICT, detail=detail, code=code)

class InternalServerErrorException(BaseException):
    def __init__(self, detail: Any = "Internal server error", code: ErrorCode | str = ErrorCode.INTERNAL_ERROR):
        super().__init__(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=detail, code=code)
