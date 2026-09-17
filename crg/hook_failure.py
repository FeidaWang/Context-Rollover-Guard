"""Event-specific hook failure outputs; diagnostics never authorize replay."""
import errno


def reason_code(exc):
    if isinstance(exc, TimeoutError):return 'CRG_HOOK_TIMEOUT'
    if isinstance(exc, PermissionError):return 'CRG_PERMISSION_DENIED'
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:return 'CRG_STORAGE_FULL'
    return 'CRG_CAPTURE_UNCONFIRMED'


def failure_output(event, exc, *, prompt_block=False, precompact_block=False):
    """Flags are adapter-verified contracts, never payload/config assertions.

    Public adapters pass false. Nonzero exit is diagnostic only, not evidence
    that a runtime rejected a prompt. Stop must never cause an answer retry.
    """
    name=event.get('hook_event_name') if isinstance(event,dict) else None
    code=reason_code(exc)
    instruction=(code+': CRG could not confirm durable capture. Retain the original input and '
                 'recovery files; inspect local state before any retry. Nothing was forwarded by CRG.')
    if name=='UserPromptSubmit' and prompt_block:
        return {'decision':'block','reason':instruction},0
    if name=='PreCompact' and precompact_block:
        return {'continue':False,'stopReason':instruction},0
    if name=='Stop':
        return {'systemMessage':instruction+' Observation/capture unavailable; ordinary work may continue.'},0
    return {'systemMessage':instruction+' CRG_BLOCKING_UNSUPPORTED: interception remains disabled.'},1
