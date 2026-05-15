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


class ExternalDependencyError(ApplicationException):
    """Excepción lanzada cuando hay un error conectando o resolviendo un proveedor externo"""
    pass
