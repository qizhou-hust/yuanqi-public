"""Read-only MCP route for the explicit finite nearest-feasible edit problem."""
from ..product.nearest_feasible_edit import AXES, propose
from ..product.system_optimize import SCOPES

REQUIRED = ('design_doc', 'system_input', 'domain', 'request')
REQUEST_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['target', 'metric', 'constraints', 'source'],
    'properties': {
        'target': {'type': 'object', 'additionalProperties': False, 'required': list(AXES),
                   'properties': {axis: {'type': 'string', 'minLength': 1} for axis in AXES}},
        'metric': {'type': 'object', 'additionalProperties': False, 'required': ['kind', 'weights'],
                   'properties': {'kind': {'type': 'string', 'enum': ['weighted_hamming']},
                                  'weights': {'type': 'object', 'additionalProperties': False,
                                              'required': list(AXES), 'properties': {
                                                  axis: {'type': 'string', 'maxLength': 128,
                                                         'pattern': r'^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$'}
                                                  for axis in AXES}}}},
        'constraints': {'type': 'object', 'additionalProperties': False, 'required': ['pass_scopes'],
                        'properties': {'pass_scopes': {'type': 'array', 'const': list(SCOPES)}}},
        'source': {'type': 'string', 'minLength': 1}}}

TOOL = {'name': 'nearest_feasible_edit',
        'description': 'Read-only finite joint nearest feasible edit. Supply source documents, full bounded domain, '
                       'explicit target IDs, positive exact decimal weights, all four pass scopes and edit source. '
                       'Weighted Hamming counts changed record IDs; no physical displacement or continuous optimum. '
                       'Returns all exact ties; never applies edits or grants commit authority.',
        'annotations': {'readOnlyHint': True},
        'inputSchema': {'type': 'object', 'additionalProperties': False,
                        'required': list(REQUIRED),
                        'properties': {**{name: {'type': 'object'} for name in REQUIRED if name != 'request'},
                                       'request': REQUEST_SCHEMA,
                                       'expected_problem_sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}}}}


def run(args):
    if not isinstance(args, dict) or not set(REQUIRED) <= set(args) or set(args) - set(REQUIRED) - {'expected_problem_sha256'}:
        return {'status': 'blocked_invalid_inputs', 'read_only': True, 'nearest': None,
                'errors': [{'code': 'invalid_arguments', 'message': 'Explicit design_doc, system_input, domain and request required; unknown fields forbidden'}]}
    return propose(**args)
