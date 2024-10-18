# authentication/utils.py

import random
import hashlib
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from .models import OTP

def send_sms(phone_number, message):
    """
    Implement this function using your preferred SMS gateway.
    For example, using Twilio:
    
    from twilio.rest import Client

    def send_sms(phone_number, message):
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )
    """
    # Placeholder implementation
    print(f"Sending SMS to {phone_number}: {message}")

def generate_otp(user):
    code = f"{random.randint(100000, 999999)}"
    otp = OTP.objects.create(user=user)
    otp.set_code(code)
    otp.save()
    send_sms(user.phone_number, f"Your OTP code is {code}")
    return otp

def verify_otp(user, code):
    try:
        otp = OTP.objects.filter(user=user, is_used=False).latest('created_at')
        if otp.is_expired():
            return False, "OTP has expired."
        if otp.check_code(code):
            otp.is_used = True
            otp.save()
            return True, "OTP verified successfully."
        else:
            return False, "Invalid OTP."
    except OTP.DoesNotExist:
        return False, "Invalid OTP."

def can_request_otp(user):
    """
    Limit OTP requests to prevent abuse.
    Example: Max 5 OTP requests per hour.
    """
    time_threshold = timezone.now() - timedelta(hours=1)
    recent_otps = OTP.objects.filter(user=user, created_at__gte=time_threshold).count()
    return recent_otps < 5  # Allow up to 5 OTP requests per hour