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


@pytest.mark.parametrize('conditions', [{}, {'fields': []}, {'field': {'name': 'Name'}}, {'text': 'Saved', 'script': 'true'}])
async def test_invalid_success_is_rejected_before_binding_dispatch(conditions):
    class Coordinator:
        def get_capability(self, name):
            pytest.fail('Invalid success conditions must not bind dispatch or call a model')
    result = await UIUseTool(Coordinator(), {}).execute({'task': 'Fill the form', 'surface': 'browser', 'success': conditions})
    assert result.success is False and result.error['type'] == 'invalid_success_conditions'
