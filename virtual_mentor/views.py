from django.http import JsonResponse
from django.db import connection

def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
        if row and row[0] == 1:
            return JsonResponse({"status": "healthy", "database": "connected"}, status=200)
        else:
            return JsonResponse({"status": "unhealthy", "database": "invalid response"}, status=500)
    except Exception as e:
        return JsonResponse({"status": "unhealthy", "database": str(e)}, status=500)