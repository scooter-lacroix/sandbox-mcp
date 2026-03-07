"""
Node.js-specific sandbox implementation for the enhanced Sandbox SDK.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from .base_sandbox import BaseSandbox
from .execution import Execution
from ..utils.lazy_imports import require_feature

if TYPE_CHECKING:
    import aiohttp


class NodeSandbox(BaseSandbox):
    """
    Node.js-specific sandbox for executing JavaScript code.

    Currently only supports remote execution via microsandbox server.
    """

    def __init__(self, **kwargs: object) -> None:
        """
        Initialize a Node.js sandbox instance.
        """
        # Require aiohttp for Node sandbox
        self._aiohttp = require_feature("Node.js sandbox", "aiohttp")
        
        # Force remote=True for Node sandboxes (no local implementation yet)
        kwargs["remote"] = True
        super().__init__(**kwargs)

    async def get_default_image(self) -> str:
        """
        Get the default Docker image for Node.js sandbox.
        """
        return "microsandbox/node"

    async def run(self, code: str) -> Execution:
        """
        Execute JavaScript code in the sandbox.

        Args:
            code: JavaScript code to execute

        Returns:
            An Execution object representing the executed code

        Raises:
            RuntimeError: If the sandbox is not started or execution fails
        """
        if not self._is_started:
            raise RuntimeError("Sandbox is not started. Call start() first.")

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        request_data = {
            "jsonrpc": "2.0",
            "method": "sandbox.repl.run",
            "params": {
                "sandbox": self._name,
                "namespace": self._namespace,
                "language": "javascript",
                "code": code,
            },
            "id": str(uuid.uuid4()),
        }

        try:
            async with self._session.post(
                f"{self._server_url}/api/v1/rpc",
                json=request_data,
                headers=headers,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Failed to execute code: {error_text}")

                response_data = await response.json()
                if "error" in response_data:
                    raise RuntimeError(
                        f"Failed to execute code: {response_data['error']['message']}"
                    )

                result = response_data.get("result", {})

                # Create and return an Execution object with the output data
                return Execution(output_data=result)
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to execute code: {e}")

    @classmethod
    async def create(
        cls,
        server_url: Optional[str] = None,
        namespace: str = "default",
        name: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs
    ):
        """
        Create a Node.js sandbox instance.

        Args:
            server_url: URL of the Microsandbox server
            namespace: Namespace for the sandbox
            name: Optional name for the sandbox
            api_key: API key for authentication
            **kwargs: Additional arguments passed to the sandbox

        Returns:
            A context manager that yields a NodeSandbox instance
        """
        return super().create(
            remote=True,
            server_url=server_url,
            namespace=namespace,
            name=name,
            api_key=api_key,
            **kwargs
        )
