# # authentication/utils.py

# import random
# from datetime import timedelta
# from django.utils import timezone
# from django.core.mail import send_mail
# from .models import OTP
# from django.contrib.auth import get_user_model
# import logging
# from chaTrip.settings import DEFAULT_FROM_EMAIL

# logger = logging.getLogger('auth')

# User = get_user_model()

# def generate_otp_code():
#     """Generate a 6-digit random OTP code."""
#     return f"{random.randint(100000, 999999)}"

# def send_otp_email(email, code):
#     """
#     Send an OTP code to the specified email address using Django's send_mail.
#     """
#     subject = "ChaTrip OTP Code"
#     message = f"Your One-Time Password (OTP) is: {code}\nThis code is valid for 5 minutes."
#     from_email = DEFAULT_FROM_EMAIL
#     recipient_list = [email]

#     try:
#         send_mail(
#             subject,
#             message,
#             from_email,
#             recipient_list,
#             fail_silently=False,
#         )
#         logger.info(f"Sent OTP to {email}.")
#     except Exception as e:
#         logger.error(f"Failed to send OTP email to {email}: {str(e)}")
#         raise e

# def generate_and_send_otp(user):
#     otp = generate_otp_code()
#     # Save OTP to the database
#     otp_record = OTP.objects.create(user=user)
#     otp_record.set_code(otp)
#     otp_record.save()
#     # Send OTP via email
#     send_otp_email(user.email, otp)

# def verify_otp(user, code):
#     """
#     Verify the provided OTP code for the user.
#     """
#     try:
#         otp = OTP.objects.filter(user=user, is_used=False).latest('created_at')
#         if otp.is_expired():
#             return False, "OTP has expired."
#         if otp.check_code(code):
#             otp.is_used = True
#             otp.save()
#             return True, "OTP verified successfully."
#         else:
#             return False, "Invalid OTP."
#     except OTP.DoesNotExist:
#         return False, "No OTP found. Please request a new one."

# def can_request_otp(user):
#     """
#     Check if the user can request a new OTP based on rate limiting.
#     Example: Max 5 OTP requests per hour.
#     """
#     time_threshold = timezone.now() - timedelta(hours=1)
#     recent_otps = OTP.objects.filter(user=user, created_at__gte=time_threshold).count()
#     return recent_otps < 5  # Allow up to 5 OTP requests per hour




# authentication/utils.py

import random
from datetime import timedelta
from django.utils import timezone
from .models import OTP
from django.contrib.auth import get_user_model
import ssl
import certifi
import smtplib
import logging
from email.message import EmailMessage
from chaTrip.settings import EMAIL_HOST_PASSWORD,EMAIL_HOST_USER 

logger = logging.getLogger('auth')

User = get_user_model()

def generate_otp_code():
    """Generate a 6-digit random OTP code."""
    return f"{random.randint(100000, 999999)}"

def generate_and_send_otp(user):
    otp = generate_otp_code()
    msg = EmailMessage()
    msg.set_content(f"Your OTP is: {otp}")
    msg['Subject'] = 'Your OTP Code'
    msg['From'] = EMAIL_HOST_USER  # Ensure this is a valid sender email
    msg['To'] = user.username

    # Create a secure SSL context using certifi
    context = ssl.create_default_context(cafile=certifi.where())

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
            server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)  # Use actual credentials
            server.send_message(msg)
        logger.info(f"Sent OTP to {user.email}.")
    except Exception as e:
        logger.error(f"Failed to send OTP email: {e}")
        raise

def verify_otp(user, code):
    """
    Verify the provided OTP code for the user.
    """
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
        return False, "No OTP found. Please request a new one."

def can_request_otp(user):
    """
    Check if the user can request a new OTP based on rate limiting.
    Example: Max 5 OTP requests per hour.
    """
    time_threshold = timezone.now() - timedelta(hours=1)
    recent_otps = OTP.objects.filter(user=user, created_at__gte=time_threshold).count()
    return recent_otps < 5  # Allow up to 5 OTP requests per hour