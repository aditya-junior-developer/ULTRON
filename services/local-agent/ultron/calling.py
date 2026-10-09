from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CallRequest:
    recipient: str
    international: bool = False


class CallingProvider(Protocol):
    """An optional adapter contract; never instantiated by the free V1 runtime."""
    def quote(self, request: CallRequest) -> dict: ...
    async def dial(self, request: CallRequest, approval_id: str) -> dict: ...
    async def status(self, call_id: str) -> dict: ...
    async def hang_up(self, call_id: str) -> dict: ...


class ZeroBudgetCalling:
    def quote(self, request: CallRequest) -> dict:
        return {"available": False, "reason": "No verified ₹0 PSTN provider is configured. Telephone calls may incur carrier/provider charges.",
                "recipient": request.recipient, "international": request.international}

    async def dial(self, request: CallRequest, approval_id: str) -> dict:
        raise ValueError("Calling is disabled under the ₹0 budget; no provider request was made")
