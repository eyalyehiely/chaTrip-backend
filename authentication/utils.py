
import random,ssl,certifi,smtplib,logging
from datetime import timedelta
from django.utils import timezone
from .models import *
from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework import status
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



    # Save OTP to the database
    otp_record = Otp.objects.create(user=user)
    otp_record.set_code(otp)
    otp_record.save()
    try:
        otp_record.save()
        logger.info(f"OTP entry saved for user: {user.email}")
    except Exception as e:
        logger.error(f"Failed to save OTP for user {user.email}: {e}")
        raise
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

def verify_otp(user, otp_code):
    """
    Verify the provided OTP code for the user.
    """
    try:
        # Fetch the latest OTP for the user
        otp = Otp.objects.filter(user=user, is_used=False).latest('created_at')
        print('value:', otp)
        
        # Check if the retrieved OTP is for the same user
        if otp.user != user:
            logger.error(f"Retrieved OTP for a different user. Expected {user.email}, but got {otp.user.email}.")
            return False, "Invalid OTP entry."

        logger.debug(f"Retrieved OTP entry: {otp} for user: {user.email}")
        
        # Check if the OTP has expired
        if otp.is_expired():
            logger.info(f"OTP expired for user: {user.email}")
            return False, "OTP has expired."
        
        # Check if the provided OTP code is correct
        if otp.check_code(otp_code):
            print(otp.check_code(otp_code))
            otp.is_used = True
            otp.save()
            logger.info(f"OTP verified successfully for user: {user.email}")
            return True, "OTP verified successfully."
        else:
            otp.attempt_count += 1
            otp.save()
            logger.warning(f"Invalid OTP code provided for user: {user.email}. Attempt {otp.attempt_count}/5")
            
            # Optional: Handle exceeding max OTP attempts
            if otp.attempt_count >= 5:
                otp.is_used = True
                otp.save()
                logger.warning(f"Maximum OTP attempts exceeded for user: {user.email}")
                return False, "Maximum OTP attempts exceeded. Please request a new OTP."
            
            return False, "Invalid OTP."
    
    except Otp.DoesNotExist:
        logger.warning(f"No OTP found for user: {user.email}")
        return False, "No OTP found. Please request a new one."
    
def can_request_otp(user):
    """
    Check if the user can request a new OTP based on rate limiting.
    Example: Max 5 OTP requests per hour.
    """
    time_threshold = timezone.now() - timedelta(hours=1)
    recent_otps = Otp.objects.filter(user=user, created_at__gte=time_threshold).count()
    return recent_otps < 5  # Allow up to 5 OTP requests per hour