class UpstreamError(Exception):
    """Зовнішній сервіс недоступний або повернув помилку."""

    def __init__(self, service: str, message: str, status: int | None = None):
        super().__init__(message)
        self.service = service
        self.message = message
        self.status = status


class CityNotFound(Exception):
    pass
