from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView
from accounts.serializers.auth import (
                          ResendOTPSerializer,
                          VerifyOTPSerializer, ForgotPasswordSerializer,
                          ResetPasswordSerializer
                          )
from accounts.models import Profile, User, OTPVerification, PasswordResetOTP
from accounts.services.user_service import send_otp, send_reset_otp
from firebase_admin import auth as firebase_auth



class GoogleLoginView(APIView):
    permission_classes = []

    def post(self, request):
        id_token = request.data.get('id_token')

        if not id_token:
            return Response(
                {'detail': 'id_token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            decoded_token = firebase_auth.verify_id_token(id_token)
        except Exception:
            return Response(
                {'detail': 'Invalid token'},
                status=status.HTTP_400_BAD_REQUEST
            )

        email = decoded_token.get('email')
        full_name = decoded_token.get('name', '')

        # تقسيم الاسم الكامل
        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'role': User.ROLE_STUDENT,
                'is_active': True,
            }
        )

        if not created and user.role != User.ROLE_STUDENT:
            return Response(
                {'detail': 'Please use the standard login'},
                status=status.HTTP_403_FORBIDDEN
            )

        profile, profile_created = Profile.objects.get_or_create(user=user)

        if created:
            profile.first_name = first_name
            profile.last_name = last_name
            profile.save()

        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.role
        refresh['user_id'] = str(user.id)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': profile.first_name,
                'last_name': profile.last_name,
                'role': user.role,
                'is_new': created,
            }
        })


# -----------------------------Activation----------------------------------------------------------------------------

@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True), name='post')
class VerifyOTPView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyOTPSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        code = serializer.validated_data['code']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'detail': 'Invalid email or code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            otp = OTPVerification.objects.get(user=user)
        except OTPVerification.DoesNotExist:
            return Response(
                {'detail': 'Invalid email or code'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if otp.attempts >= 5:
            otp.delete()
            return Response(
                {'detail': 'Too many attempts, please request a new code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if otp.is_expired():
            return Response({'detail': 'Code has expired'}, status=status.HTTP_400_BAD_REQUEST)

        if otp.code != code:
            otp.attempts += 1
            otp.save()
            return Response(
                {'detail': 'Invalid email or code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.is_active = True
        user.save()
        otp.delete()

        return Response({'detail': 'Account activated successfully'})

@method_decorator(ratelimit(key='ip', rate='3/m', method='POST', block=True), name='post')
class ResendOTPView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ResendOTPSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'detail': 'If this email exists, a new code has been sent'},
                status=status.HTTP_200_OK
            )

        if user.is_active:
            return Response(
                {'detail': 'Account is already activated'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            otp = OTPVerification.objects.get(user=user)
            if otp.is_on_cooldown():
                return Response(
                    {'detail': 'Please wait 2 minutes before requesting a new code'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
        except OTPVerification.DoesNotExist:
            pass

        send_otp(user)
        return Response({'detail': 'If this email exists, a new code has been sent'})    

# ---------------------------Reset-Password--------------------------------------------------------------------------

@method_decorator(ratelimit(key='ip', rate='3/m', method='POST', block=True), name='post')
class ForgotPasswordView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'detail': 'If this email exists, a reset code has been sent'},
                status=status.HTTP_200_OK
            )
        
        try:
            otp = PasswordResetOTP.objects.get(user=user)
            if otp.is_on_cooldown():
                return Response(
                    {'detail': 'Please wait 2 minutes before requesting a new code'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
        except PasswordResetOTP.DoesNotExist:
            pass

        send_reset_otp(user)
        return Response({'detail': 'If this email exists, a reset code has been sent'})


@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True), name='post')
class ResetPasswordView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        new_password = serializer.validated_data['new_password']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'detail': 'Invalid email or code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            otp = PasswordResetOTP.objects.get(user=user)
        except PasswordResetOTP.DoesNotExist:
            return Response(
                {'detail': 'Invalid email or code'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if otp.attempts >= 5:
            otp.delete()
            return Response(
                {'detail': 'Too many attempts, please request a new code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if otp.is_expired():
            return Response(
                {'detail': 'Code has expired'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if otp.code != code:
            otp.attempts += 1
            otp.save()
            return Response(
                {'detail': 'Invalid email or code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()
        otp.delete()

        return Response({'detail': 'Password reset successfully'})