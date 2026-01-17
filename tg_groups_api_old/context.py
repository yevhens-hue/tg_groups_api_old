# context.py
import contextvars

# request id for current async task (per-request)
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
