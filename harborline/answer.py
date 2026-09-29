"""Retrieve, guard, and optionally generate a cited answer."""

from __future__ import annotations

from harborline.config import Settings, get_settings
from harborline.guardrails import apply_guardrails
from harborline.prompts import SYSTEM_PROMPT, user_prompt
from harborline.rerank import rerank_hits
from harborline.retrieve import Hit, build_retriever
from harborline.rewrite import rewrite_query


def retrieve_hits(
    query: str,
    employee_id: str | None = None,
    kind: str | None = None,
    source_format: str | None = None,
    settings: Settings | None = None,
    retriever: object | None = None,
) -> tuple[list[Hit], str]:
    settings = settings or get_settings()
    retriever = retriever or build_retriever(settings)
    search_query = rewrite_query(query) if settings.rewrite_queries else query
    pool = retriever.search(
        search_query,
        top_k=settings.fetch_k,
        employee_id=employee_id,
        kind=kind,
        source_format=source_format,
    )
    if settings.rerank:
        hits = rerank_hits(query, pool, settings.top_k)
    else:
        hits = pool[: settings.top_k]
    return hits, search_query


def _citation_payload(hits: list[Hit]) -> list[dict]:
    return [
        {
            "n": i,
            "chunk_id": h.chunk.chunk_id,
            "source_path": h.chunk.source_path,
            "source_format": h.chunk.source_format,
            "title": h.chunk.title,
            "section": h.chunk.section,
            "snippet": h.chunk.snippet,
            "kind": h.chunk.kind,
            "score": round(h.score, 4),
        }
        for i, h in enumerate(hits, start=1)
    ]


def retrieve_answer(query: str, hits: list[Hit]) -> str:
    lines = [
        f"Query: {query}",
        "",
        "**Policy fact** (extractive; no model API key used):",
        "The numbered sources below are the supporting snippets. "
        "They are policy text, not personal advice.",
        "",
        "**Citations**",
        "",
    ]
    for i, hit in enumerate(hits, start=1):
        lines.append(
            f"[{i}] {hit.chunk.title} — {hit.chunk.section} "
            f"({hit.chunk.source_path}, score={hit.score:.3f})\n"
            f"    {hit.chunk.snippet}"
        )
    lines.append("")
    lines.append(
        "**Not a recommendation:** Use these rules with your manager or "
        "hr@harborline.example; this tool does not decide exceptions."
    )
    return "\n".join(lines)


def _openai_client(settings: Settings):
    from openai import OpenAI

    key = settings.require_llm_key()
    client_kwargs = {"api_key": key}
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**client_kwargs)


def _complete(settings: Settings, system: str, user: str) -> str:
    client = _openai_client(settings)
    response = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0,
        seed=settings.seed,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def llm_answer(query: str, hits: list[Hit], settings: Settings, employee_id: str | None) -> str:
    return _complete(settings, SYSTEM_PROMPT, user_prompt(query, hits, employee_id))


def _format_dict_sources(sources: list[dict]) -> str:
    if not sources:
        return "(none)"
    blocks = []
    for i, src in enumerate(sources, start=1):
        blocks.append(
            f"[{i}] title={src.get('title')}\n"
            f"section={src.get('section')}\n"
            f"path={src.get('source_path')}\n"
            f"snippet={src.get('snippet') or src.get('text') or ''}"
        )
    return "\n\n".join(blocks)


_REWRITE_SYSTEM = SYSTEM_PROMPT + """
The draft and tool notes already checked Harborline records through MCP tools.
Keep every concrete fact from the draft that appears in the tool notes or sources:
employee names, ids, balances, dates, verdicts, and any MOCK or confirmation status.
Do not add policy numbers, amounts, or dates that are not in the draft or sources.
"""


def llm_rewrite_answer(
    query: str,
    draft: str,
    sources: list[dict],
    tool_notes: list[str],
    settings: Settings,
    employee_id: str | None,
) -> str:
    """Turn an MCP tool draft into a cited model answer. Requires OPENAI_API_KEY."""
    notes = "\n".join(f"- {note}" for note in tool_notes) or "(none)"
    who = employee_id or "(none)"
    user = (
        f"Question:\n{query}\n\n"
        f"Employee id: {who}\n\n"
        f"Tool notes:\n{notes}\n\n"
        f"Draft answer (facts already checked):\n{draft}\n\n"
        f"Retrieved sources:\n{_format_dict_sources(sources)}\n"
    )
    return _complete(settings, _REWRITE_SYSTEM, user)


def ask(
    query: str,
    employee_id: str | None = None,
    kind: str | None = None,
    source_format: str | None = None,
    settings: Settings | None = None,
    retriever: object | None = None,
) -> dict:
    settings = settings or get_settings()
    hits, rewritten = retrieve_hits(
        query,
        employee_id=employee_id,
        kind=kind,
        source_format=source_format,
        settings=settings,
        retriever=retriever,
    )
    ok, refusal = apply_guardrails(query, hits, settings.min_score)
    mode = settings.answer_mode if settings.answer_mode == "llm" else "retrieve"
    if not ok:
        text = refusal or ""
        mode = "refused"
    elif settings.answer_mode == "llm":
        text = llm_answer(query, hits, settings, employee_id)
    else:
        text = retrieve_answer(query, hits)
    return {
        "query": query,
        "rewritten_query": rewritten,
        "employee_id": employee_id,
        "mode": mode,
        "guardrail_ok": ok,
        "answer": text,
        "sources": _citation_payload(hits if ok else []),
    }
