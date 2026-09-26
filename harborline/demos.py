"""Two fixed People Desk tasks shared by the chat UI and API clients.

Each task is a different multi-step workflow. The question, employee id, and
tool path are fixed so POST /demos/{id} and POST /chat return the same answer
and the same policy citations on every call.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoTask:
    id: str
    label: str
    blurb: str
    query: str
    employee_id: str
    citation_source: str

    def as_dict(self) -> dict:
        chat = {"query": self.query, "employee_id": self.employee_id}
        return {
            "id": self.id,
            "label": self.label,
            "blurb": self.blurb,
            "query": self.query,
            "employee_id": self.employee_id,
            "citation_source": self.citation_source,
            "chat": chat,
            "curl": f"curl -X POST http://127.0.0.1:8000/demos/{self.id}",
        }


DEMOS: tuple[DemoTask, ...] = (
    DemoTask(
        id="remote-emp-1008",
        label="Demo 1 · Remote eligibility · EMP-1008",
        blurb=(
            "Looks up Alex Kim, reads the hub location rule in POL-RMT-003, "
            "and checks that fully remote work needs a People Ops reclass."
        ),
        query="Am I eligible for fully remote work living in Tacoma?",
        employee_id="EMP-1008",
        citation_source="03-remote-hybrid-work.md",
    ),
    DemoTask(
        id="benefits-emp-1008",
        label="Demo 2 · Benefits election · EMP-1008",
        blurb=(
            "Looks up Alex Kim's HarborHub medical plan and 401(k) deferral, "
            "then cites the medical and retirement sections of POL-BEN-006."
        ),
        query="What medical plan and 401k deferral do I have?",
        employee_id="EMP-1008",
        citation_source="06-employee-benefits.md",
    ),
)


def get_demo(demo_id: str) -> DemoTask | None:
    for demo in DEMOS:
        if demo.id == demo_id:
            return demo
    return None
