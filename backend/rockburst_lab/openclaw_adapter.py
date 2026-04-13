from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class AgentInvocation:
    name: str
    role: str
    prompt: str
    observation: dict[str, Any]


class OpenClawRuntime:
    """Runtime boundary for OpenClaw-backed specialist agents."""

    def __init__(self) -> None:
        self.mode = os.getenv("OPENCLAW_MODE", "local").lower()
        self.provider = "local-openclaw-adapter"
        self.client: Any | None = None
        if self.mode == "sdk":
            self.client = self._try_build_sdk_client()

    def invoke(
        self,
        invocation: AgentInvocation,
        fallback: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        if self.client is not None:
            sdk_result = self._invoke_sdk(invocation)
            if sdk_result is not None:
                return sdk_result

        result = fallback()
        result["agent"] = invocation.name
        result["openclaw_runtime"] = {
            "mode": "local_fallback",
            "provider": self.provider,
        }
        return result

    def _try_build_sdk_client(self) -> Any | None:
        try:
            module = importlib.import_module("openclaw")
        except ImportError:
            self.provider = "openclaw-sdk-not-installed"
            return None

        api_key = os.getenv("OPENCLAW_API_KEY")
        base_url = os.getenv("OPENCLAW_BASE_URL")
        for class_name in ("Client", "OpenClaw", "OpenClawClient"):
            client_class = getattr(module, class_name, None)
            if client_class is None:
                continue
            try:
                if api_key and base_url:
                    self.provider = f"openclaw.{class_name}"
                    return client_class(api_key=api_key, base_url=base_url)
                if api_key:
                    self.provider = f"openclaw.{class_name}"
                    return client_class(api_key=api_key)
                self.provider = f"openclaw.{class_name}"
                return client_class()
            except TypeError:
                continue
        self.provider = "openclaw-sdk-unrecognized"
        return None

    def _invoke_sdk(self, invocation: AgentInvocation) -> dict[str, Any] | None:
        payload = {
            "agent": invocation.name,
            "role": invocation.role,
            "prompt": invocation.prompt,
            "observation": invocation.observation,
        }
        for method_name in ("run_agent", "invoke", "run"):
            method = getattr(self.client, method_name, None)
            if not callable(method):
                continue
            try:
                response = method(payload)
            except TypeError:
                try:
                    response = method(**payload)
                except Exception:
                    continue
            except Exception:
                continue
            if isinstance(response, dict):
                response.setdefault("agent", invocation.name)
                response.setdefault(
                    "openclaw_runtime",
                    {"mode": "sdk", "provider": self.provider},
                )
                return response
        return None
