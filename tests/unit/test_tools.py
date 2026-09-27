import pytest
from pydantic import ValidationError

from supply_lab.ai.tools import ToolCall


def test_specialist_cannot_call_another_specialists_tool():
    with pytest.raises(ValidationError):
        ToolCall(agent="demand", tool="propose_orders", day=0, source_ids=["data"])
