import logging
import re
import time
import uuid

from fastapi import Request
from starlette.responses import Response

logger = logging.getLogger("yieldsense.request")

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def resolve_request_id(header_value: str | None) -> str:
    """Reuse a client request ID only if it is short and plain.

    Accepting any value let clients write fake log lines (for example
    by including a newline).
    """
    if header_value and REQUEST_ID_PATTERN.match(header_value):
        return header_value

    return str(uuid.uuid4())


def resolve_client_ip(request: Request) -> str:
    """Return the caller's IP address.

    Behind Azure App Service, request.client is the platform's proxy;
    the original client is the first entry of X-Forwarded-For. This value
    is only used for logging.
    """
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    first_hop = forwarded_for.split(",")[0].strip()

    if first_hop:
        # Azure may append the client port, e.g. "203.0.113.5:51234".
        if first_hop.count(":") == 1:
            first_hop = first_hop.split(":")[0]

        return sanitize_for_log(first_hop)

    return request.client.host if request.client else "unknown"


def sanitize_for_log(value: str) -> str:
    return CONTROL_CHARACTERS.sub("?", value)


async def request_logging_middleware(
    request: Request,
    call_next,
) -> Response:
    """
    Log incoming requests, response status, client IP, request ID,
    and execution time.

    Request bodies and authorization headers are intentionally not logged.
    """
    request_id = resolve_request_id(request.headers.get("X-Request-ID"))

    start_time = time.perf_counter()

    client_ip = resolve_client_ip(request)

    method = request.method
    path = request.url.path

    if request.url.query:
        path = f"{path}?{request.url.query}"

    path = sanitize_for_log(path)

    logger.info(
        "request_started | request_id=%s | method=%s | path=%s | client_ip=%s",
        request_id,
        method,
        path,
        client_ip,
    )

    try:
        response = await call_next(request)

    except Exception:
        duration_ms = (
            time.perf_counter() - start_time
        ) * 1000

        logger.exception(
            "request_failed | request_id=%s | method=%s | path=%s "
            "| client_ip=%s | duration_ms=%.2f",
            request_id,
            method,
            path,
            client_ip,
            duration_ms,
        )

        raise

    duration_ms = (
        time.perf_counter() - start_time
    ) * 1000

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-MS"] = f"{duration_ms:.2f}"

    log_method = (
        logger.error
        if response.status_code >= 500
        else logger.warning
        if response.status_code >= 400
        else logger.info
    )

    log_method(
        "request_completed | request_id=%s | method=%s | path=%s "
        "| status=%s | duration_ms=%.2f",
        request_id,
        method,
        path,
        response.status_code,
        duration_ms,
    )

    return response