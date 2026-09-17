"""Fail-closed boundary for legacy live experiments; no account/config reads.

A separately reviewed runtime adapter must enforce budgets and inspect effective
hooks before these historical experiments may be enabled again. An environment
variable, CLI flag, config file or fixture is not evidence of that contract.
"""


class LivePolicyError(RuntimeError):
    pass


def verify_effective_hooks(actual, expected):
    """Exact inventory, including disabled entries; unknown metadata is not safe.

    Caller must obtain actual from current runtime hooks/list for every effective
    source before thread creation. Expected is explicitly reviewed run scope,
    never learned from the actual inventory. No trust bypass is permitted.
    """
    if not isinstance(actual,list) or not isinstance(expected,list) or actual!=expected:
        raise LivePolicyError('CRG_UNKNOWN_EFFECTIVE_HOOKS')
    for entry in actual:
        if not isinstance(entry,dict) or entry.get('enabled') is not True or entry.get('trustStatus')!='trusted':
            raise LivePolicyError('CRG_UNVERIFIED_HOOK_TRUST')


def require_live_authorization(entrypoint):
    """Legacy entrypoints are unavailable, even with user consent alone.

    Required future run contract: explicit authorization, selected model, maximum
    model calls (including compaction/retries), enforceable token or monetary cap,
    total deadline/cancellation policy, exact effective hook allowlist, and typed
    export scope. Existing transports provide none of the complete contract.
    Keep this rejection before filesystem mutation, real HOME reads and launch.
    """
    raise LivePolicyError(
        'CRG_LIVE_DISABLED_UNVERIFIED_CONTRACT: '+entrypoint+
        '; explicit authorization, model/call/token-or-cost limits, deadline, '
        'effective-hook allowlist and export scope require a reviewed runtime adapter. '
        'Do not bypass trust or retry an ambiguously accepted request.')
