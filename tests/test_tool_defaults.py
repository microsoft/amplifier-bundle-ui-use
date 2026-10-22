"""Core integration metadata makes optional runtime selection visible to planners."""
import pytest

pytest.importorskip('amplifier_core')
from amplifier_module_tool_ui_use import UIUseTool


def test_planner_sees_effective_default_without_backend_credentials():
    ordinary = UIUseTool(None, {})
    selected = UIUseTool(None, {'selection': {'browser': {'mode': 'decision', 'backend': 'private-label'}}})
    assert '"browser": "standard"' in ordinary.description
    assert '"browser": "decision"' in selected.description
    assert '"computer": "standard"' in selected.description
    assert 'private-label' not in selected.description
    assert 'Omit' in selected.input_schema['properties']['mode']['description']
