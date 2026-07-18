"""`alfred demo` — instrumented fake agent (Brique 6).

See PLAN.md §5 Brique 6 and
docs/adr/0008-brique6-demo-launch-polish-design.md.
"""

from __future__ import annotations

from alfred.demo.fake_agent import build_demo_payload, demo_mandate

__all__ = ["build_demo_payload", "demo_mandate"]
