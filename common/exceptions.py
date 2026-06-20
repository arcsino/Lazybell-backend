from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return None

    if isinstance(response.data, dict):
        if 'detail' in response.data and len(response.data) == 1:
            response.data = {'error': str(response.data['detail'])}
        elif 'non_field_errors' in response.data:
            response.data = {
                'error': 'Validation error',
                'errors': response.data,
            }
        elif response.status_code == status.HTTP_400_BAD_REQUEST:
            response.data = {
                'error': 'Validation error',
                'errors': response.data,
            }
    elif isinstance(response.data, list):
        response.data = {'error': 'Validation error', 'errors': response.data}

    return response
