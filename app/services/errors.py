class IntegrationUnavailableError(RuntimeError):
    """Raised when a required MVP module has not been integrated yet."""


class IntegrationContractError(RuntimeError):
    """Raised when an integrated module violates the agreed contract."""
