"""LLM Gateway exceptions."""


class LlmGatewayException(Exception):
    """Base for всіх LLM gateway exceptions."""


class OperationNotConfiguredException(LlmGatewayException):
    """Operation_id не знайдений у llm_routing.yml."""

    def __init__(self, operation_id: str) -> None:
        super().__init__(
            f"operation_id '{operation_id}' not configured in llm_routing.yml. "
            f"Add to operations: section."
        )
        self.operation_id = operation_id


class KillSwitchActiveException(LlmGatewayException):
    """Kill switch engaged — всі LLM calls rejected."""

    def __init__(self, reason: str | None = None, engaged_at: str | None = None) -> None:
        msg = "kill switch engaged"
        if engaged_at:
            msg += f" at {engaged_at}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)
        self.reason = reason


class BudgetExceededException(LlmGatewayException):
    """Daily budget cap reached."""

    def __init__(
        self,
        cap_usd: float,
        spent_usd: float,
        attempted_usd: float | None = None,
    ) -> None:
        msg = f"daily budget cap ${cap_usd:.2f} would be exceeded (spent ${spent_usd:.4f}"
        if attempted_usd is not None:
            msg += f", attempted +${attempted_usd:.4f}"
        msg += ")"
        super().__init__(msg)
        self.cap_usd = cap_usd
        self.spent_usd = spent_usd
        self.attempted_usd = attempted_usd
