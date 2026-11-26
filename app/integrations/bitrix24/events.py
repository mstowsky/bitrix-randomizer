"""REST API client for Bitrix24 event subscriptions."""

import httpx


class Bitrix24EventAPIError(Exception):
    """Error returned by the Bitrix24 REST API."""

    def __init__(self, error: str, description: str) -> None:
        self.error = error
        self.description = description
        super().__init__(f"Bitrix24 API error: {error}")


class Bitrix24EventClient:
    """Client for managing Bitrix24 event subscriptions."""

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    async def get_event_handlers(
        self,
        client_endpoint: str,
        access_token: str,
    ) -> list[dict[str, object]]:
        """Return event handlers registered by the application."""
        response_data = await self._request(
            client_endpoint=client_endpoint,
            method="event.get",
            access_token=access_token,
        )

        result = response_data.get("result")
        if not isinstance(result, list):
            raise ValueError("Invalid response from Bitrix24 event.get.")

        return result

    async def bind_event(
        self,
        client_endpoint: str,
        access_token: str,
        event: str,
        handler: str,
    ) -> bool:
        """Register an online event handler."""
        response_data = await self._request(
            client_endpoint=client_endpoint,
            method="event.bind",
            access_token=access_token,
            params={
                "event": event,
                "handler": handler,
            },
        )

        result = response_data.get("result")
        if not isinstance(result, bool):
            raise ValueError("Invalid response from Bitrix24 event.bind.")

        return result

    async def ensure_event_handler(
        self,
        client_endpoint: str,
        access_token: str,
        event: str,
        handler: str,
    ) -> bool:
        """Ensure that the specified event handler is registered."""
        handlers = await self.get_event_handlers(
            client_endpoint=client_endpoint,
            access_token=access_token,
        )

        for registered_handler in handlers:
            if (
                registered_handler.get("event") == event
                and registered_handler.get("handler") == handler
                and registered_handler.get("offline") == 0
            ):
                return False

        return await self.bind_event(
            client_endpoint=client_endpoint,
            access_token=access_token,
            event=event,
            handler=handler,
        )

    async def _request(
        self,
        client_endpoint: str,
        method: str,
        access_token: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, object]:
        """Send an authenticated REST request to Bitrix24."""
        if not client_endpoint or not access_token:
            raise ValueError("Bitrix24 endpoint and access token are required.")

        url = f"{client_endpoint.rstrip('/')}/{method}"
        payload: dict[str, str] = {"auth": access_token}

        if params:
            payload.update(params)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)

        try:
            response_data = response.json()
        except ValueError as exc:
            raise ValueError("Invalid JSON response from Bitrix24.") from exc

        if not isinstance(response_data, dict):
            raise ValueError("Invalid response from Bitrix24.")

        if response_data.get("error"):
            raise Bitrix24EventAPIError(
                error=str(response_data["error"]),
                description=str(response_data.get("error_description", "")),
            )

        response.raise_for_status()
        return response_data
