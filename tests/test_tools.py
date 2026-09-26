import asyncio
import importlib.util

from harborline.config import get_settings
from harborline.ingest import load_chunks
from harborline.mcp_server import MCP_TOOL_NAMES, create_server
from harborline.retrieve import TfidfRetriever
from harborline.tools import (
    check_policy_compliance,
    check_pto_balance,
    create_mock_hr_ticket,
    draft_hr_email,
    get_policy_section,
    lookup_benefits_status,
    lookup_employee_profile,
    reset_mocks,
    search_policy_documents,
)


def _tfidf():
    settings = get_settings()
    return TfidfRetriever(load_chunks(settings), settings)


def test_lookup_employee_profile_found():
    payload = lookup_employee_profile("emp-1008")
    assert payload["found"] is True
    assert payload["employee"]["legal_name"] == "Alex Kim"


def test_lookup_employee_profile_missing():
    payload = lookup_employee_profile("EMP-9999")
    assert payload["found"] is False
    assert "No HarborHub profile" in payload["error"]


def test_check_pto_and_benefits_mock_rows():
    pto = check_pto_balance("EMP-1008")
    assert pto["found"] is True
    assert pto["pto"]["eligible_to_use"] is True
    benefits = lookup_benefits_status("EMP-1008")
    assert benefits["found"] is True
    assert benefits["benefits"]["election_status"]


def test_search_policy_documents_returns_hits():
    payload = search_policy_documents("PTO carryover 40 hours", kind="policy", retriever=_tfidf())
    assert payload["tool"] == "search_policy_documents"
    assert payload["hits"]
    assert payload["rewritten_query"]


def test_get_policy_section_by_id():
    payload = get_policy_section("POL-PTO-001", section="Eligibility")
    assert payload["found"] is True
    assert payload["sections"]
    assert "fallback" not in payload
    assert {section["source_path"] for section in payload["sections"]} == {"corpus/01-paid-time-off.md"}
    assert all("Eligibility" in section["section"] for section in payload["sections"])


def test_check_policy_compliance_uses_rag_and_mock():
    payload = check_policy_compliance(
        "Am I eligible for fully remote work?",
        employee_id="EMP-1008",
        policy_id="POL-RMT-003",
        retriever=_tfidf(),
    )
    assert payload["tool"] == "check_policy_compliance"
    assert payload["evidence"]
    assert payload["employee_found"] is True
    assert payload["verdict"] in {"noncompliant_if_fully_remote", "needs_review", "noncompliant"}


def test_irreversible_actions_are_mock_until_confirm():
    reset_mocks()
    pending = create_mock_hr_ticket("pto_request", "Need Friday off", employee_id="EMP-1008")
    assert pending["status"] == "pending_confirmation"
    assert pending["id"] is None
    created = create_mock_hr_ticket(
        "pto_request", "Need Friday off", employee_id="EMP-1008", confirm=True
    )
    assert created["status"] == "mock_created"
    assert created["id"].startswith("MOCK-TCK-")
    assert created["draft"]["writes_to_harborhub"] is False

    msg = draft_hr_email("EMP-1008", "PTO", "Please approve PTO")
    assert msg["status"] == "pending_confirmation"


def test_mcp_server_exposes_at_least_five_named_tools():
    if importlib.util.find_spec("mcp") is None:
        return
    server = create_server()
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert set(MCP_TOOL_NAMES) <= names
    assert len(names) >= 5
    assert "search_policy_documents" in names
    assert "create_mock_hr_ticket" in names
