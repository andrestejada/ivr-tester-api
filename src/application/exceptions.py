class ApplicationException(Exception):
    pass


class NotFoundError(ApplicationException):
    pass


class ConflictError(ApplicationException):
    pass


class ForbiddenError(ApplicationException):
    pass


class BusinessValidationError(ApplicationException):
    pass
