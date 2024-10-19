# authentication/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .serializers import EmailSerializer, OTPSerializer
from .utils import generate_and_send_otp, verify_otp, can_request_otp
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
import logging



logger = logging.getLogger('auth')  # Updated to match the logger in utils.py
User = get_user_model()

@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated users to request OTPs
def send_otp_email_view(request):
    logger.info("Received request to send OTP email.")
    serializer = EmailSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        logger.debug(f"Validated email: {email}")
        try:
            user = User.objects.filter(username=email).first()
            if user:
                logger.info(f"Found existing user for email: {email}")
            else:
                logger.info(f"No existing user found for email: {email}. Creating a new user.")
                user = User.objects.create(username=email)
                user.set_unusable_password()
                user.save()
                logger.debug(f"Created new user with email: {email}")
        except Exception as e:
            logger.error(f"Error querying or creating user for email {email}: {str(e)}")
            return Response({"detail": "Internal server error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not can_request_otp(user):
            logger.warning(f"OTP request limit exceeded for user: {email}")
            return Response(
                {"detail": "OTP request limit exceeded. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        try:
            generate_and_send_otp(user)
            logger.info(f"OTP generated and sent to email: {email}")
            return Response({"detail": "OTP sent successfully to your email."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Failed to send OTP to email {email}: {str(e)}")
            return Response({"detail": "Failed to send OTP. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    logger.warning(f"Invalid serializer data: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated users to verify OTPs
def verify_otp_email_view(request):
    logger.info("Received request to verify OTP.")
    serializer = OTPSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        logger.debug(f"Validated data - Email: {email}, OTP Code: {code}")

        try:
            user = User.objects.filter(username=email).first()
            logger.info(f"Found user for OTP verification: {email}")
        except User.DoesNotExist:
            logger.warning(f"User with email {email} does not exist.")
            return Response({"detail": "User with this email does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            success, message = verify_otp(user, code)
            if success:
                logger.info(f"OTP verified successfully for user: {email}")
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                refresh['username'] = user.username
                logger.debug(f"Generated JWT tokens for user: {email}")
                return Response({
                    "detail": message,
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }, status=status.HTTP_200_OK)
            
            else:
                logger.warning(f"OTP verification failed for user: {email}. Reason: {message}")
                return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error during OTP verification for user {email}: {str(e)}")
            return Response({"detail": "Internal server error during OTP verification."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    logger.warning(f"Invalid serializer data: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)