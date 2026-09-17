"""Runtime catalog projections and explicit, scoped execution-parameter preparation."""
import copy
from dataclasses import asdict, dataclass
from datetime import datetime
from .domain import now
from .ledger import identity, timestamp


@dataclass(frozen=True)
class ModelCapability:
    id: str
    family: str | None
    available: bool
    reasoning_efforts: tuple[str, ...]
    context_window: int | None  # Catalog metadata only; never active context or a limit.
    provider: str | None
    service_tiers: tuple[str, ...]
    source: str
    observed_at: str
    display_name: str | None = None
    default_effort: str | None = None
    migration_hint: str | None = None
    published_api_window: int | None = None
    context_window_runtime: int | None = None
    context_status: str = 'UNKNOWN'
    compact_limit_runtime: int | None = None
    compact_limit_scope: str = 'UNKNOWN'
    native_continuity: str = 'UNKNOWN'


def normalize_model(entry, *, observed_at, source='model/list'):
    if not isinstance(entry, dict):
        raise ValueError('Catalog entry must be an object')
    ident = entry.get('id')
    if not isinstance(ident, str) or not ident:
        raise ValueError('Catalog entry requires an explicit ID')
    def optional(key):
        value = entry.get(key)
        return value if isinstance(value, str) and value else None
    def values(key, field):
        items = entry.get(key, [])
        if not isinstance(items, list):
            raise ValueError('Invalid catalog dimension: ' + key)
        items = [x.get(field) if isinstance(x, dict) else x for x in items]
        if any(not isinstance(x, str) or not x for x in items):
            raise ValueError('Invalid catalog dimension value: ' + key)
        return tuple(dict.fromkeys(items))
    efforts = values('supportedReasoningEfforts', 'reasoningEffort')
    tiers = values('serviceTiers', 'id')
    context = entry.get('contextWindow')
    available = entry.get('available', True) is True and entry.get('hidden', False) is False
    default = optional('defaultReasoningEffort')
    return ModelCapability(ident, optional('family'), available, efforts,
        context if type(context) is int and context > 0 else None, optional('provider'),
        tiers, source, observed_at, optional('displayName'), default if default in efforts else None,
        optional('upgrade'))  # Informational only; never redirect or auto-migrate an ID.


def runtime_binding(schema, *, auth_mode, account_scope_id, client_surface):
    """Trusted adapter supplies an opaque scope, never credentials or display labels.

    This reads local evidence only. Callers must independently establish current auth
    scope; it is not inferred from a model listing, file path, or account configuration.
    """
    from .capability_evidence import validate
    for value in (auth_mode, account_scope_id, client_surface):
        if not isinstance(value, str) or not value or value.lower() in {'unknown', 'unverified'}:
            raise ValueError('Verified runtime/account scope required')
    validate(schema.manifest, schema.schema_root, binary=schema.runtime_binary,
             surface=client_surface, for_action=True)
    return dict(binary_sha256=schema.manifest['binary_sha256'],
                execution_runtime_version=schema.runtime_version,
                schema_sha256=identity(schema.manifest['schema_sha256']),
                client_surface=client_surface, auth_mode=auth_mode, account_scope_id=account_scope_id,
                evidence_grade='schema_and_runtime_bound')


def discover_models(request, schema, *, max_pages=20, binding=None):
    """Only schema-validated read requests; unknown scope makes this observation-only."""
    observed = now()
    result = {'status': 'UNKNOWN', 'observed_at': observed, 'source': 'model/list', 'models': [],
              'binding': None, 'automatic_actions_allowed': False}
    if 'model/list' not in schema.methods:
        return dict(result, reason='METHOD_UNAVAILABLE')
    cursor = None; seen = set(); entries = {}
    try:
        if type(max_pages) is not int or not 1 <= max_pages <= 100:
            raise ValueError('Invalid catalog page budget')
        if binding is not None:
            actual = runtime_binding(schema, **{k: binding[k] for k in
                                     ('auth_mode', 'account_scope_id', 'client_surface')})
            if actual != binding:
                raise ValueError('Catalog runtime scope changed')
            result['binding'] = copy.deepcopy(actual)
        for _ in range(max_pages):
            params = {} if cursor is None else {'cursor': cursor}
            schema.validate_action('model/list', params)
            page = request('model/list', params)
            if not isinstance(page, dict) or not isinstance(page.get('data'), list):
                raise ValueError('Invalid catalog page')
            for raw in page['data']:
                model = normalize_model(raw, observed_at=observed)
                if model.id in entries and entries[model.id] != asdict(model):
                    raise ValueError('Conflicting model metadata')
                entries[model.id] = asdict(model)
            cursor = page.get('nextCursor')
            if cursor is None:
                if binding is not None and runtime_binding(schema, **{k: binding[k] for k in
                        ('auth_mode', 'account_scope_id', 'client_surface')}) != binding:
                    raise ValueError('Runtime changed during pagination')
                return dict(result, status='VERIFIED_CATALOG', models=list(entries.values()))
            if not isinstance(cursor, str) or not cursor or cursor in seen:
                raise ValueError('Invalid/repeated cursor')
            seen.add(cursor)
        raise ValueError('Catalog page budget exceeded')
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, AttributeError):
        return dict(result, binding=None, reason='INCOMPLETE_OR_UNSUPPORTED_CATALOG')


def resolve_action(catalog, *, model_id, effort, at, expected_revision=None,
                   schema=None, binding=None, authorized_params=None,
                   execution_mode='single_agent', service_tier=None, permission_profile=None):
    """Prepare (never send) one explicit turn under an already authorized envelope.

    Model and effort may change by explicit request. Every other wire field is copied
    exactly from authorized_params. Mode, tier and permission choices cannot expand
    this envelope. Trusted adapters must recheck account scope before dispatch.
    """
    result = {'status': 'UNAVAILABLE', 'action': None, 'automatic_switch': False}
    try:
        age = (datetime.fromisoformat(timestamp(at)) -
               datetime.fromisoformat(timestamp(catalog['observed_at']))).total_seconds()
        current_age = (datetime.fromisoformat(now()) -
                       datetime.fromisoformat(timestamp(catalog['observed_at']))).total_seconds()
        if catalog.get('status') != 'VERIFIED_CATALOG' or not 0 <= age <= 3600 or not 0 <= current_age <= 3600:
            return dict(result, reason='CATALOG_UNKNOWN_OR_STALE')
        if not isinstance(model_id, str) or not model_id:
            raise ValueError('Explicit runtime model ID required')
        matches = [m for m in catalog['models'] if m['id'] == model_id]
        if len(matches) != 1 or matches[0].get('available') is not True:
            return dict(result, reason='MODEL_NOT_UNIQUELY_AVAILABLE')
        model = matches[0]
        efforts = model.get('reasoning_efforts', ())
        if (not isinstance(efforts, (list, tuple))
                or not all(isinstance(value, str) and value for value in efforts)
                or not isinstance(effort, str) or not effort or effort not in efforts):
            return dict(result, reason='EFFORT_NOT_EXPOSED')
        if schema is None or binding is None or not isinstance(authorized_params, dict):
            return dict(result, reason='CURRENT_EXECUTION_CONTRACT_REQUIRED')
        actual = runtime_binding(schema, **{k: binding[k] for k in
                                 ('auth_mode', 'account_scope_id', 'client_surface')})
        if actual != binding or catalog.get('binding') != actual:
            return dict(result, reason='RUNTIME_OR_ACCOUNT_SCOPE_CHANGED')
        if execution_mode != 'single_agent':
            return dict(result, reason='EXECUTION_MODE_NOT_AUTHORIZED')
        if (permission_profile != authorized_params.get('permissions') or
                service_tier != authorized_params.get('serviceTier') or
                not (permission_profile or isinstance(authorized_params.get('sandboxPolicy'), dict))):
            return dict(result, reason='EXECUTION_ENVELOPE_CHANGED_OR_UNKNOWN')
        if service_tier is not None:
            tiers = model.get('service_tiers', ())
            if (not isinstance(tiers, (list, tuple)) or not isinstance(service_tier, str)
                    or not all(isinstance(tier, str) and tier for tier in tiers) or service_tier not in tiers):
                return dict(result, reason='SERVICE_TIER_NOT_EXPOSED')
        if model.get('provider') is not None and model['provider'] != authorized_params.get('modelProvider'):
            return dict(result, reason='MODEL_PROVIDER_NOT_AUTHORIZED')
        metadata = {key: model.get(key) for key in ('id', 'family', 'available', 'reasoning_efforts',
                                                  'context_window', 'provider', 'service_tiers', 'migration_hint')}
        revision = identity({'model': metadata, 'binding': actual})
        if expected_revision is not None and expected_revision != revision:
            return dict(result, reason='CAPABILITIES_CHANGED', capability_revision=revision,
                        reset_estimator=True)
        params = copy.deepcopy(authorized_params)
        params.update(model=model_id, effort=effort)
        schema.validate_action('turn/start', params)
        action = dict(model_id=model_id, reasoning_effort=effort, execution_mode=execution_mode,
                      service_tier=service_tier, permission_profile=permission_profile)
        return dict(result, status='RESOLVED', action=action, wire_params=params,
                    capability_revision=revision, capabilities=metadata,
                    evidence_source=catalog.get('source'), catalog_age_seconds=age,
                    binding=actual, requires_dispatch_revalidation=True)
    except (OSError, RuntimeError, KeyError, TypeError, ValueError, AttributeError):
        return dict(result, reason='INVALID_CATALOG_OR_EXECUTION_CONTRACT')
