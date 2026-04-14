"""MCP stdio server — Model Context Protocol integration for Claude Code."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

# MCP protocol types
JSONRPC_REQUEST = "2.0"
MCP_VERSION = "2024-11-05"


class MCPError(Exception):
    """MCP protocol error."""
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


class AgentResult:
    """Mock AgentResult-like object for MCP gate evaluations."""

    def __init__(self, file_contents: dict | None = None):
        self.verification_commands = ["verified via MCP"]
        self.text = "Files reviewed"
        self.file_contents = file_contents or {}


class MCPSTDIOServer:
    """MCP server using stdio transport.

    Implements the JSON-RPC 2.0 message protocol over stdin/stdout.
    Claude Code's MCP integration communicates via this protocol.
    """

    def __init__(self, name: str = "effort"):
        self.name = name
        self.logger = logging.getLogger(f"mcp.{name}")
        self._handlers: dict[str, callable] = {}
        self._tools: dict[str, dict] = {}
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register the MCP protocol request handlers."""
        self._handlers["initialize"] = self._handle_initialize
        self._handlers["tools/list"] = self._handle_tools_list
        self._handlers["tools/call"] = self._handle_tools_call
        self._handlers["shutdown"] = self._handle_shutdown

    def _register_tools(self) -> None:
        """Register available MCP tools."""

        self._tools = {
            "effort__gate": {
                "name": "effort__gate",
                "description": "Evaluate a task and return PASS/REDO/FAIL verdict. "
                              "Checks for shortcuts, skipped verification, single-pass "
                              "completion, and 'good enough' language. Returns verdict "
                              "with reasoning and specific issues found.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Description of the task being evaluated.",
                        },
                        "level": {
                            "type": "string",
                            "description": "Effort level: efficient, thorough, exhaustive, perfectionist. Default: thorough.",
                        },
                        "file_contents": {
                            "type": "object",
                            "description": "Map of filename to file content for scanning.",
                        },
                    },
                    "required": ["task"],
                },
            },
            "effort__lint": {
                "name": "effort__lint",
                "description": "Validate an effort.md file for contradictions and missing sections.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "project_root": {
                            "type": "string",
                            "description": "Path to the project root (default: cwd).",
                        },
                    },
                },
            },
            "effort__explain": {
                "name": "effort__explain",
                "description": "Mentor mode: explain WHY a specific issue caused a REDO verdict.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "issue": {
                            "type": "string",
                            "description": "The issue description to explain.",
                        },
                        "verdict": {
                            "type": "string",
                            "description": "The verdict this issue caused (done, redo, fail).",
                        },
                    },
                    "required": ["issue"],
                },
            },
        }

    async def _handle_initialize(self, params: dict) -> dict:
        """Handle MCP initialize request."""
        return {
            "protocolVersion": MCP_VERSION,
            "serverInfo": {
                "name": self.name,
                "version": "0.1.0",
            },
            "capabilities": {
                "tools": {},
            },
        }

    async def _handle_tools_list(self, params: dict) -> dict:
        """Handle tools/list request."""
        self._register_tools()
        tools = [
            {"name": name, **tool}
            for name, tool in self._tools.items()
        ]
        return {"tools": tools}

    async def _handle_tools_call(self, params: dict) -> dict:
        """Handle tools/call request."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name == "effort__gate":
            result = await self._tool_gate(arguments)
        elif tool_name == "effort__lint":
            result = self._tool_lint(arguments)
        elif tool_name == "effort__explain":
            result = self._tool_explain(arguments)
        else:
            raise MCPError(-32602, f"Unknown tool: {tool_name}")

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2, default=str),
                }
            ]
        }

    async def _tool_gate(self, args: dict) -> dict:
        """Run effort gate evaluation via MCP tool."""

        from effort_agent import EffortAgent, EffortConfig, EffortVerdict

        project_root = Path(args.get("project_root", ".")).resolve()
        level = args.get("level", "thorough")
        config = EffortConfig(enabled=True, level=level, require_effort_md=False)
        agent = EffortAgent(config=config)

        file_contents = args.get("file_contents", {})
        agent_result = AgentResult(file_contents=file_contents)

        result = agent.evaluate(
            task=args.get("task", "MCP evaluation"),
            agent_result=agent_result,
            file_contents=file_contents,
        )
        return {
            "verdict": result.verdict.value if isinstance(result.verdict, EffortVerdict) else result.verdict,
            "reasoning": result.reasoning,
            "issues": result.issues,
            "effort_level": result.effort_level,
            "verification_evidence_found": result.verification_evidence_found,
            "draft_count": result.draft_count,
            "shortcut_phrases_found": result.shortcut_phrases_found,
            "category": result.category,
            "principle_violated": result.principle_violated,
        }

    def _tool_lint(self, args: dict) -> dict:
        """Lint effort.md via MCP tool."""
        import re

        from effort_agent.models.effort_spec import EffortSpec

        project_root = Path(args.get("project_root", ".")).resolve()
        spec_path = project_root / "effort.md"

        if not spec_path.exists():
            return {"valid": False, "issues": ["effort.md not found"]}

        try:
            content = spec_path.read_text(encoding="utf-8", errors="replace")
            spec = EffortSpec.from_markdown(content)
        except Exception as e:
            return {"valid": False, "issues": [str(e)]}

        issues = []
        if not spec.process_philosophy or not spec.process_philosophy.text.strip():
            issues.append("Section '1. Process Philosophy' is empty or missing")

        if not spec.verification_requirements or not spec.verification_requirements.requirements:
            issues.append("Section '2. Verification Requirements' is empty or missing")

        if not spec.iteration_standards:
            issues.append("Section '3. Iteration Standards' is empty or missing")

        if not spec.forbidden_shortcuts or not spec.forbidden_shortcuts.shortcuts:
            issues.append("Section '4. Forbidden Shortcuts' is empty or missing")

        if not spec.effort_levels:
            issues.append("Section '5. Effort Levels' is missing or has no valid levels")

        return {"valid": len(issues) == 0, "issues": issues}

    def _tool_explain(self, args: dict) -> dict:
        """Mentor explain via MCP tool."""
        issue_text = args.get("issue", "")
        verdict = args.get("verdict", "redo")
        # Simple canned explanations keyed by issue pattern
        explanations = {
            "skipped_verification": "Verification commands prove the work was actually tested. Running 'pytest', checking output, or validating the build proves you did the work — not just that you wrote code.",
            "good_enough_language": "'Good enough' is a shortcut. When you say 'should work' or 'good enough for now', you're skipping the last mile of rigor. Thorough work doesn't hedge.",
            "single_pass": "One-pass completion means you skipped iteration. The first draft is never the best. Review, refine, and verify before claiming done.",
            "missing_research": "Implementation without research is guesswork. You must search docs, check patterns, and understand constraints before writing code.",
            "missing_effort_md": "effort.md defines the contract for this project. Without it, there's no shared standard for what 'done' means.",
            "insufficient_drafts": "The iteration standard requires multiple drafts. A single pass almost always misses edge cases and subtle bugs.",
            "placeholder_code": "Placeholder or TODO code signals incomplete work. Everything must be implemented — not left as a reminder for later.",
            "assumptions": "Unverified assumptions become bugs. Always validate your assumptions before presenting them as conclusions.",
            "vague_copy": "Vague language signals unclear thinking. Replace 'it works' with specific evidence: 'pytest passed with 47 tests, 0 failures'.",
            "shortcut_language": "Shortcuts compound. Each 'good enough' today becomes tomorrow's bug report. Build the habit of full completion.",
        }
        # Find matching explanation
        explanation = None
        issue_lower = issue_text.lower()
        for key, exp in explanations.items():
            if key in issue_lower:
                explanation = exp
                break

        if explanation is None:
            explanation = (
                "This issue violates the process integrity standard. "
                "Effort-agent exists to catch shortcuts before they compound. "
                "Address it thoroughly before claiming the task is done."
            )

        return {
            "issue": issue_text,
            "verdict": verdict,
            "why_this_matters": explanation,
            "guidance": "Fix the root cause, not just the symptom. Run verification, iterate, and confirm full completion.",
        }

    async def _handle_shutdown(self, params: dict) -> dict:
        """Handle shutdown request."""
        return {"success": True}

    async def run(self) -> None:
        """Run the MCP stdio server loop."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                self._send_error(-32700, "Parse error")
                continue

            result = await self._handle_request(request)
            if result is not None:
                print(json.dumps(result), flush=True)

    async def _handle_request(self, request: dict) -> dict | None:
        """Handle a single JSON-RPC request. Returns response dict or None for notifications."""
        # Missing method key is a different error than unknown method
        if "method" not in request:
            return {"jsonrpc": JSONRPC_REQUEST, "id": request.get("id"), "error": {"code": -32600, "message": "Invalid Request: method is required"}}

        method = request.get("method", "")
        params = request.get("params", {})
        msg_id = request.get("id")

        handler = self._handlers.get(method)
        if not handler:
            error = {"jsonrpc": JSONRPC_REQUEST, "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
            return error if msg_id is not None else None

        try:
            result = await handler(params)
            if msg_id is None:
                return None  # Notification — no response
            return {"jsonrpc": JSONRPC_REQUEST, "id": msg_id, "result": result}
        except MCPError as e:
            return {"jsonrpc": JSONRPC_REQUEST, "id": msg_id, "error": {"code": e.code, "message": e.message, "data": e.data}}
        except Exception as e:
            self.logger.exception("Handler error")
            return {"jsonrpc": JSONRPC_REQUEST, "id": msg_id, "error": {"code": -32603, "message": f"Internal error: {e}"}}

    # For backward compatibility with tests that call _handle directly
    async def _handle(self, request: dict) -> dict | None:
        """Handle a single JSON-RPC request (test interface)."""
        return await self._handle_request(request)

    def _send_response(self, msg_id: Any, result: Any) -> None:
        """Send a JSON-RPC response."""
        response = {
            "jsonrpc": JSONRPC_REQUEST,
            "id": msg_id,
            "result": result,
        }
        print(json.dumps(response), flush=True)

    def _send_error(self, code: int, message: str, msg_id: Any = None, data: Any = None) -> None:
        """Send a JSON-RPC error."""
        response = {
            "jsonrpc": JSONRPC_REQUEST,
            "id": msg_id,
            "error": {
                "code": code,
                "message": message,
                "data": data,
            },
        }
        print(json.dumps(response), flush=True)


def main() -> None:
    """Entry point for MCP server."""
    logging.basicConfig(level=logging.WARNING)
    server = MCPSTDIOServer("effort")
    import asyncio
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
