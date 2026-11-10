from rest_framework.views import exception_handler


def _flatten(data):
    """Return a short human readable message from DRF error data."""
    if isinstance(data, dict):
        if "detail" in data:
            return str(data["detail"])
        for key, value in data.items():
            msg = _flatten(value)
            if msg:
                return msg if key in ("non_field_errors",) else f"{key}: {msg}"
    elif isinstance(data, (list, tuple)) and data:
        return _flatten(data[0])
    elif data:
        return str(data)
    return ""


def custom_exception_handler(exc, context):
    """Uniform error format: {"success": false, "message": "...", "errors": {...}}"""
    response = exception_handler(exc, context)
    if response is not None:
        errors = response.data
        response.data = {
            "success": False,
            "message": _flatten(errors) or "Request failed",
            "errors": errors,
        }
    return response
