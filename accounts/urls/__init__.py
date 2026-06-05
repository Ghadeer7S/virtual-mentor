from django.urls import path, include

urlpatterns = [
    path('', include('accounts.urls.auth')),
    path('', include('accounts.urls.profile')),
]