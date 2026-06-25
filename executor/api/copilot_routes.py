"""
AI Copilot routes — Processes scan data and answers user queries using an LLM API.
"""
import logging
import json
import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from executor.persistence.database import get_db_session
from executor.persistence.models import Scan, Task, ScanResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["copilot"])


class CopilotRequest(BaseModel):
    scan_id: Optional[str] = None
    query: str
    context_view: str = "executive_dashboard"


class CopilotResponse(BaseModel):
    answer: str
    evidence: list = []
    suggestions: list = []


async def _gather_scan_context(scan_id: str, db: AsyncSession) -> Dict[str, Any]:
    """Gathers live scan data to build context for the LLM."""
    context: Dict[str, Any] = {}

    # Fetch scan
    stmt = select(Scan).where(Scan.id == scan_id)
    result = await db.execute(stmt)
    scan = result.scalar_one_or_none()
    if not scan:
        return {"error": f"Scan {scan_id} not found"}

    context["scan"] = {
        "id": str(scan.id),
        "name": scan.name,
        "target": scan.target,
        "status": scan.status,
        "created_at": scan.created_at.isoformat() if scan.created_at else None,
    }

    # Task stats
    stmt_stats = (
        select(Task.status, func.count(Task.id))
        .where(Task.scan_id == scan_id)
        .group_by(Task.status)
    )
    result_stats = await db.execute(stmt_stats)
    task_stats = {status: count for status, count in result_stats.all()}
    context["task_stats"] = task_stats
    context["total_tasks"] = sum(task_stats.values())

    # Sample tasks with responses (limit to most relevant 20)
    stmt_tasks = (
        select(Task)
        .where(Task.scan_id == scan_id)
        .order_by(Task.created_at.desc())
        .limit(20)
    )
    result_tasks = await db.execute(stmt_tasks)
    tasks = result_tasks.scalars().all()

    task_summaries = []
    for task in tasks:
        # Load response
        stmt_resp = select(ScanResponse).where(ScanResponse.task_id == task.id)
        res_resp = await db.execute(stmt_resp)
        resp = res_resp.scalar_one_or_none()

        summary = {
            "method": task.method,
            "url": task.url,
            "status": task.status,
            "attempts": task.attempts,
        }
        if resp:
            summary["response_status_code"] = resp.status_code
            summary["latency_ms"] = resp.latency_ms
            summary["error_message"] = resp.error_message
            # Include truncated body for context
            if resp.response_body:
                summary["response_body_preview"] = resp.response_body[:500]

        task_summaries.append(summary)

    context["tasks"] = task_summaries

    # Failures summary
    failed_tasks = [t for t in task_summaries if t["status"] == "FAILED"]
    context["failed_tasks_count"] = len(failed_tasks)
    context["failed_tasks_sample"] = failed_tasks[:5]

    # Unique endpoints
    unique_endpoints = set()
    for task in tasks:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(task.url)
            unique_endpoints.add(f"{task.method} {parsed.path}")
        except Exception:
            unique_endpoints.add(f"{task.method} {task.url}")
    context["unique_endpoints"] = list(unique_endpoints)
    context["endpoint_count"] = len(unique_endpoints)

    return context


def _build_system_prompt(context: Dict[str, Any], context_view: str) -> str:
    """Builds a system prompt for the LLM based on scan context."""
    return f"""You are a cybersecurity AI assistant for an API Security Testing Platform called TrustLayer API Studio.
You analyze REAL scan data and provide expert security insights. Never make up findings — only reference actual data provided.

Current scan context:
- Scan: {context.get('scan', {}).get('name', 'None')}
- Target: {context.get('scan', {}).get('target', 'None')}
- Status: {context.get('scan', {}).get('status', 'None')}
- Total Tasks: {context.get('total_tasks', 0)}
- Task Status Breakdown: {json.dumps(context.get('task_stats', {}))}
- Unique Endpoints: {context.get('endpoint_count', 0)}
- Failed Tasks: {context.get('failed_tasks_count', 0)}
- Current View: {context_view}

Recent task details (most recent 20):
{json.dumps(context.get('tasks', []), indent=2, default=str)[:3000]}

Rules:
1. Base ALL answers on the actual scan data above.
2. If no scan data exists, say so clearly.
3. Provide actionable security recommendations.
4. Reference specific endpoints and status codes from the data.
5. Be concise but thorough. Use bullet points.
6. If asked about vulnerabilities, analyze the response codes, error messages, and patterns.
7. Suggest follow-up actions the user should take."""


async def _call_llm(system_prompt: str, user_query: str) -> str:
    """Calls an external LLM API (Gemini/OpenAI compatible)."""
    import httpx

    # Try Gemini first, then OpenAI
    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    logger.info(
        f"GEMINI_API_KEY found: {bool(gemini_key)}"
    )
    
    logger.info(
        f"OPENAI_API_KEY found: {bool(openai_key)}"
    )
    if gemini_key:
        logger.info("Using Gemini API")
        return await _call_gemini(
            gemini_key,
            system_prompt,
            user_query,
        )
    
    if openai_key:
        logger.info("Using OpenAI API")
        return await _call_openai(
            openai_key,
            system_prompt,
            user_query,
        )
    
    logger.warning("No LLM API key found. Using fallback.")
    
    return _rule_based_fallback(
        system_prompt,
        user_query,
    )


async def _call_gemini(api_key: str, system_prompt: str, user_query: str) -> str:
    """Calls Gemini API."""
    import httpx

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": f"{system_prompt}\n\nUser Question: {user_query}"}]}
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 1024,
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        if response.status_code != 200:
            logger.error(
                f"Gemini API error "
                f"{response.status_code}: "
                f"{response.text}"
            )
        
            raise Exception(
                f"Gemini API failed: {response.text}"
            )

        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return _rule_based_fallback(system_prompt, user_query)


async def _call_openai(api_key: str, system_prompt: str, user_query: str) -> str:
    """Calls OpenAI API."""
    import httpx

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
    
    except httpx.TimeoutException:
        logger.exception("Gemini timeout")
        return _rule_based_fallback(
            system_prompt,
            user_query,
        )
    
    except Exception:
        logger.exception("Gemini failed")
        return _rule_based_fallback(
            system_prompt,
            user_query,
        )


def _rule_based_fallback(system_prompt: str, user_query: str) -> str:
    """Rule-based fallback when no LLM API key is configured."""
    query_lower = user_query.lower()

    if "critical" in query_lower or "most critical" in query_lower:
        return "To identify the most critical endpoint, I analyze task failure patterns and HTTP response codes from your scan data. Endpoints returning 500-series errors or those with BOLA/BFLA patterns (where unauthorized roles receive 200 OK responses) are the highest risk. Please check the scan context above for specific endpoints. Configure a GEMINI_API_KEY or OPENAI_API_KEY environment variable for deeper AI-powered analysis."

    if "fail" in query_lower or "error" in query_lower:
        return "I can see task failure data in your scan. Failed tasks typically indicate either target API errors (5xx), authentication failures (401/403), or network timeouts. Check the Async Execution view for detailed error messages on each failed task. Configure a GEMINI_API_KEY or OPENAI_API_KEY for intelligent root-cause analysis."

    if "authorization" in query_lower or "bola" in query_lower or "privilege" in query_lower:
        return "Authorization issues are detected by comparing responses across different role contexts. If a low-privilege role receives the same sensitive data as an admin role (both 200 OK with matching fields), it indicates BOLA or Privilege Escalation. Use the Role Swapper and Diff Engine views to inspect these patterns. Configure a GEMINI_API_KEY or OPENAI_API_KEY for AI-powered vulnerability assessment."

    if "summary" in query_lower or "executive" in query_lower or "report" in query_lower:
        return "I can generate an executive summary from your live scan results. Navigate to the Security Reports view and click 'Regenerate Report' to create a comprehensive vulnerability assessment. The report includes OWASP API Top 10 mapping, CVSS scores, and remediation guidance. Configure a GEMINI_API_KEY or OPENAI_API_KEY for AI-generated narrative summaries."

    return "I'm your Security Copilot. I analyze your live scan data to answer security questions. For full AI-powered analysis, configure a GEMINI_API_KEY or OPENAI_API_KEY environment variable. You can ask me about specific endpoints, vulnerabilities, failures, or request remediation guidance."


@router.post("/copilot/ask", response_model=CopilotResponse)
async def ask_copilot(request: CopilotRequest, db: AsyncSession = Depends(get_db_session)):
    """AI Copilot endpoint — analyzes live scan data and answers user queries."""
    context: Dict[str, Any] = {}
    evidence: list = []

    # Gather scan context if scan_id is provided
    if request.scan_id:
        context = await _gather_scan_context(request.scan_id, db)
        if "error" in context:
            # Still answer but note the scan wasn't found
            pass
        else:
            # Extract evidence for the response
            evidence = context.get("failed_tasks_sample", [])

    # Build prompts and call LLM
    system_prompt = _build_system_prompt(context, request.context_view)

    try:
        answer = await _call_llm(system_prompt, request.query)
    except Exception as e:
        logger.error(f"Copilot LLM call failed: {e}")
        answer = _rule_based_fallback(system_prompt, request.query)

    # Generate follow-up suggestions based on context
    suggestions = []
    if context.get("failed_tasks_count", 0) > 0:
        suggestions.append("Show me the failed task details")
    if context.get("endpoint_count", 0) > 0:
        suggestions.append("Which endpoints are most at risk?")
    if context.get("total_tasks", 0) > 0:
        suggestions.append("Generate an executive summary")
    if not suggestions:
        suggestions = [
            "How do I start a scan?",
            "What types of vulnerabilities can you detect?",
            "Explain BOLA and BFLA"
        ]

    return CopilotResponse(
        answer=answer,
        evidence=evidence,
        suggestions=suggestions
    )
