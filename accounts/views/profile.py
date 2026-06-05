from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from djoser.permissions import CurrentUserOrAdmin
from accounts.serializers.profile import ProfileSerializer
from accounts.models import Profile

class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [CurrentUserOrAdmin]
    http_method_names = ['get', 'patch']

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Profile.objects.all()
        return Profile.objects.filter(user=user)

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        profile = Profile.objects.get(user=request.user)
        if request.method == 'GET':
            serializer = ProfileSerializer(profile)
            return Response(serializer.data)
        elif request.method == 'PATCH':
            serializer = ProfileSerializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)