
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from .serializers import PhoneNumberSerializer, OTPSerializer
from .utils import generate_otp, verify_otp, can_request_otp
from rest_framework_simplejwt.tokens import RefreshToken
# from ratelimit.decorators import ratelimit

User = get_user_model()

@api_view(['POST'])
# @ratelimit(key='ip', rate='5/m', block=True)
def send_otp(request):
    """
    Send an OTP to the provided phone number.
    """
    serializer = PhoneNumberSerializer(data=request.data)
    if serializer.is_valid():
        phone_number = serializer.validated_data['phone_number']
        user, created = User.objects.get_or_create(phone_number=phone_number)
        
        if not can_request_otp(user):
            return Response(
                {"detail": "OTP request limit exceeded. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        generate_otp(user)
        return Response({"detail": "OTP sent successfully."}, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
# @ratelimit(key='ip', rate='10/m', block=True) 
def verify_otp_view(request):
    """
    Verify the OTP for the provided phone number.
    """
    serializer = OTPSerializer(data=request.data)
    if serializer.is_valid():
        phone_number = serializer.validated_data['phone_number']
        code = serializer.validated_data['code']
        
        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response({"detail": "User does not exist."}, status=status.HTTP_400_BAD_REQUEST)
        
        success, message = verify_otp(user, code)
        if success:
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            return Response({
                "detail": message,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }, status=status.HTTP_200_OK)
        else:
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)