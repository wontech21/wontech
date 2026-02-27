from flask import jsonify


def api_success(data=None, **kwargs):
    """Standard success response envelope."""
    response = {'success': True}
    if data is not None:
        response['data'] = data
    response.update(kwargs)
    return jsonify(response)


def api_error(message, status_code=400, **kwargs):
    """Standard error response envelope."""
    response = {'success': False, 'error': message}
    response.update(kwargs)
    return jsonify(response), status_code
