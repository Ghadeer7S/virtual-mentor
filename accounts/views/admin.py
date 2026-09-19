from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import User, Profile
from accounts.serializers.admin import (
    DashboardTokenSerializer,
    DashboardUserSerializer,
    DashboardUserCreateSerializer,
    DashboardProfileSerializer,
    DeleteAccountSerializer,
)
from accounts.permissions import IsAdminOnly, IsEditorOnly
from accounts.pagination import DynamicPagination
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Auth
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class DashboardLoginView(TokenObtainPairView):
    serializer_class = DashboardTokenSerializer


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Users
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class DashboardUserViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']
    pagination_class = DynamicPagination
    filter_backends = [
        DjangoFilterBackend,
        SearchFilter
    ]
    filterset_fields = ['role', 'profile__gender']
    search_fields = [
        'email',
        'profile__first_name',
        'profile__last_name',
        'profile__phone',
        'profile__address'
    ]
    
    def get_permissions(self):
        if self.action == 'me':
            return [(IsAdminOnly | IsEditorOnly)()]
        return [IsAdminOnly()]

    def get_serializer_class(self):
        if self.action == 'create':
            return DashboardUserCreateSerializer
        return DashboardUserSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return User.objects.all().order_by('id')
        return User.objects.filter(id=user.id)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance == request.user:
            admin_count = User.objects.filter(role='admin').count()
            if admin_count <= 1:
                return Response(
                    {'detail': 'Cannot delete the last admin account.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get', 'patch', 'delete'])
    def me(self, request):
        if request.method == 'GET':
            serializer = DashboardUserSerializer(
                request.user,
                context={'request': request}
            )
            return Response(serializer.data)

        elif request.method == 'PATCH':
            serializer = DashboardUserSerializer(
                request.user,
                data=request.data,
                partial=True,
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        
        elif request.method == 'DELETE':
            if request.user.role == 'admin':
                admin_count = User.objects.filter(role='admin').count()
                if admin_count <= 1:
                    return Response(
                        {'detail': 'Cannot delete the last admin account.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            serializer = DeleteAccountSerializer(
                data=request.data,
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)

            request.user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
    
    def list(self, request, *args, **kwargs):

        pagination = request.query_params.get(
            'pagination',
            'false'
        ).lower() == 'true'

        queryset = self.filter_queryset(self.get_queryset())

        if not pagination:

            serializer = self.get_serializer(
                queryset,
                many=True
            )

            return Response(serializer.data)

        page = self.paginate_queryset(queryset)

        serializer = self.get_serializer(
            page,
            many=True
        )

        return self.get_paginated_response(serializer.data)



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Profiles
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class DashboardProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all().order_by('id')
    serializer_class = DashboardProfileSerializer
    http_method_names = ['get', 'patch']

    def get_permissions(self):
        if self.action == 'me':
            return [(IsAdminOnly | IsEditorOnly)()]
        return [IsAdminOnly()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Profile.objects.all().order_by('id')
        return Profile.objects.filter(user=user)

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        profile = Profile.objects.get(user=request.user)

        if request.method == 'GET':
            serializer = DashboardProfileSerializer(profile)
            return Response(serializer.data)

        elif request.method == 'PATCH':
            serializer = DashboardProfileSerializer(
                profile,
                data=request.data,
                partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)