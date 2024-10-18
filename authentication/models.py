from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid,hashlib
from django.utils import timezone

class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(unique=True, max_length=15, blank=True, null=True)

    def __str__(self):
        return self.username


class OTP(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    code_hash = models.CharField(max_length=64)  # SHA-256 hash
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def set_code(self, code):
        self.code_hash = hashlib.sha256(code.encode()).hexdigest()

    def check_code(self, code):
        return self.code_hash == hashlib.sha256(code.encode()).hexdigest()

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)  # OTP valid for 5 minutes

    def __str__(self):
        return f"OTP for {self.user.username}"