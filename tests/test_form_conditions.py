"""All requested values must be observed, including unchecked/mixed controls."""
import pytest
from amplifier_ui_use.controller import verify_conditions


def observation():
    return {'state': {'url': 'https://example.test/form', 'text': 'Form', 'elements': [
        {'name': 'Name', 'value': 'Ada'},
        {'name': 'Team', 'value': 'blue'},
        {'name': 'Notifications', 'value': 'on', 'checked': False, 'indeterminate': False},
        {'name': 'Consent', 'value': 'on', 'checked': True, 'indeterminate': False},
    ]}}


async def test_all_fields_and_exact_checked_states_are_verified():
    obs = observation()
    conditions = {'fields': [{'name': 'Name', 'value': 'Ada'}, {'name': 'Team', 'value': 'blue'},
                            {'name': 'Notifications', 'checked': False}, {'name': 'Consent', 'checked': True}]}
    assert await verify_conditions(obs, conditions)
    obs['state']['elements'][2]['checked'] = True
    assert not await verify_conditions(obs, conditions)


@pytest.mark.parametrize('checked,indeterminate', [(True, True), (False, True), ('mixed', None)])
async def test_mixed_is_neither_checked_nor_unchecked(checked, indeterminate):
    obs = {'state': {'elements': [{'name': 'Choice', 'checked': checked, 'indeterminate': indeterminate}]}}
    assert await verify_conditions(obs, {'field': {'name': 'Choice', 'checked': 'mixed'}})
    for wanted in (True, False):
        assert not await verify_conditions(obs, {'field': {'name': 'Choice', 'checked': wanted}})


@pytest.mark.parametrize('field', [{'name': 'Notifications', 'checked': False}, {'name': 'Consent', 'checked': True}])
async def test_absent_or_invalid_checked_state_is_not_evidence(field):
    for value in (None, '', 0, 1, 'false', 'true'):
        obs = {'state': {'elements': [{'name': field['name'], 'checked': value}]}}
        assert not await verify_conditions(obs, {'field': field})
    assert not await verify_conditions({'state': {'elements': [{'name': field['name']}]}}, {'field': field})


async def test_ambiguous_labels_do_not_prove_a_field_value():
    obs = observation()
    obs['state']['elements'].append({'name': 'Name', 'value': 'Other'})
    assert not await verify_conditions(obs, {'field': {'name': 'Name', 'value': 'Ada'}})


@pytest.mark.parametrize('conditions', [
    {'fields': []}, {'fields': {}}, {'field': {'name': 'Name'}},
    {'fields': [{'name': 'Name', 'value': 'Ada'}, {'name': 'Name', 'value': 'Ada'}]},
    {'fields': [{'name': 'Consent', 'checked': 1}]}, {'field': {'name': 'Name', 'unknown': True}},
    {'url': ''}, {'text': ''}, {}, {'fields': [{'name': 'Name', 'value': 'Ada'}] * 121},
])
async def test_malformed_conditions_never_pass(conditions):
    assert not await verify_conditions(observation(), conditions)
