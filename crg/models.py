"""Runtime-catalog projections; model names carry no capability meaning."""
from dataclasses import asdict, dataclass
from .domain import now


@dataclass(frozen=True)
class ModelCapability:
    id: str
    family: str | None
    available: bool
    reasoning_efforts: tuple[str, ...]
    context_window: int | None
    provider: str | None
    service_tiers: tuple[str, ...]
    source: str
    observed_at: str


def normalize_model(entry, *, observed_at, source='model/list'):
    ident = entry.get('id')
    if not isinstance(ident, str) or not ident:
        raise ValueError('Catalog entry requires an explicit ID')
    def optional(key):
        value = entry.get(key)
        return value if isinstance(value, str) and value else None
    def strings(value):
        return tuple(dict.fromkeys(x for x in value if isinstance(x, str) and x)) if isinstance(value, list) else ()
    efforts = entry.get('supportedReasoningEfforts', [])
    if isinstance(efforts, list):
        efforts = [x.get('reasoningEffort') if isinstance(x, dict) else x for x in efforts]
    tiers=entry.get('serviceTiers',[])
    if isinstance(tiers,list):tiers=[x.get('id') if isinstance(x,dict) else x for x in tiers]
    context = entry.get('contextWindow')
    # Catalog membership is availability evidence unless the runtime explicitly disables/hides it.
    available = entry.get('available', True) is True and entry.get('hidden', False) is False
    return ModelCapability(ident, optional('family'), available, strings(efforts),
        context if type(context) is int and context > 0 else None, optional('provider'),
        strings(tiers), source, observed_at)


def discover_models(request, schema, *, max_pages=20):
    """Bounded read-only discovery; incomplete/drifted catalogs are not recommendations."""
    observed = now()
    result = {'status': 'UNKNOWN', 'observed_at': observed, 'source': 'model/list', 'models': []}
    if 'model/list' not in schema.methods:
        result['reason'] = 'METHOD_UNAVAILABLE'
        return result
    cursor = None; seen = set(); entries = {}
    try:
        for _ in range(max_pages):
            params = {} if cursor is None else {'cursor': cursor}
            schema.validate('model/list', params)
            page = request('model/list', params)
            if not isinstance(page.get('data'), list): raise ValueError('Invalid catalog page')
            for raw in page['data']:
                model = normalize_model(raw, observed_at=observed)
                if model.id in entries and entries[model.id] != asdict(model):
                    raise ValueError('Conflicting model metadata')
                entries[model.id] = asdict(model)
            cursor = page.get('nextCursor')
            if cursor is None:
                return dict(result, status='VERIFIED_CATALOG', models=list(entries.values()))
            if not isinstance(cursor, str) or not cursor or cursor in seen: raise ValueError('Invalid/repeated cursor')
            seen.add(cursor)
        raise ValueError('Catalog page budget exceeded')
    except (ValueError, RuntimeError, KeyError, TypeError, AttributeError):
        return dict(result, reason='INCOMPLETE_OR_UNSUPPORTED_CATALOG')


def resolve_action(catalog, *, model_id, effort, at, expected_revision=None):
    """Bind an explicitly requested action to fresh runtime metadata, never its name.

    This adapter does not switch models. A changed metadata revision requires a
    fresh decision and a new estimator group, even if the model ID is unchanged.
    """
    from datetime import datetime
    from .ledger import identity, timestamp
    result = {'status': 'UNAVAILABLE', 'action': None, 'automatic_switch': False}
    try:
        age = (datetime.fromisoformat(timestamp(at)) -
               datetime.fromisoformat(timestamp(catalog['observed_at']))).total_seconds()
        if catalog.get('status') != 'VERIFIED_CATALOG' or not 0 <= age <= 3600:
            return dict(result, reason='CATALOG_UNKNOWN_OR_STALE')
        matches = [m for m in catalog['models'] if m['id'] == model_id]
        if len(matches) != 1 or matches[0].get('available') is not True:
            return dict(result, reason='MODEL_NOT_UNIQUELY_AVAILABLE')
        model = matches[0]
        efforts = model.get('reasoning_efforts', ())
        if (not isinstance(efforts, (list, tuple))
                or not all(isinstance(value, str) and value for value in efforts)
                or not isinstance(effort, str) or not effort or effort not in efforts):
            return dict(result, reason='EFFORT_NOT_EXPOSED')
        metadata = {key: model.get(key) for key in ('id', 'family', 'available', 'reasoning_efforts',
                                                  'context_window', 'provider', 'service_tiers')}
        revision = identity(metadata)
        if expected_revision is not None and expected_revision != revision:
            return dict(result, reason='CAPABILITIES_CHANGED', capability_revision=revision,
                        reset_estimator=True)
        return dict(result, status='RESOLVED', action={'model_id': model_id, 'effort': effort},
                    capability_revision=revision, capabilities=metadata,
                    evidence_source=catalog.get('source'), catalog_age_seconds=age)
    except (KeyError, TypeError, ValueError, AttributeError):
        return dict(result, reason='INVALID_CATALOG')
