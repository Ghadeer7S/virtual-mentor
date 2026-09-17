from rest_framework.views import exception_handler as drf_exception_handler

def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return response

    data = response.data
    message = None

    if isinstance(data, dict):
        for value in data.values():
            message = value[0] if isinstance(value, list) and value else value
            if message:
                break
    elif isinstance(data, list) and data:
        message = data[0]

    response.data = {'detail': str(message) if message else 'حدث خطأ غير متوقع'}
    return response