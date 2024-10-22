# authentication/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid, hashlib
from django.utils import timezone
from datetime import timedelta
import datetime
# from django.contrib.postgres.fields import JSONField


class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.EmailField(unique=True)
    saving_places = models.JSONField(default=list, blank=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []  

    def __str__(self):
        return self.username


class Otp(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    code_hash = models.CharField(max_length=64)  # SHA-256 hash
    created_at = models.DateTimeField(auto_now_add=True)
    attempt_count = models.IntegerField(default=0)
    is_used = models.BooleanField(default=False)

    def set_code(self, code):
        self.code_hash = hashlib.sha256(code.encode()).hexdigest()
        self.save()
        

    def check_code(self, code):
        input_hash = hashlib.sha256(code.encode()).hexdigest()
        print(f"Checking OTP: stored hash {self.code_hash}, input hash {input_hash}")
        return self.code_hash == input_hash

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)  # OTP valid for 5 minutes
    
    # def delete_function(self):
    #     if self.is_expired:
    #         self.delete()
    # use with celery ?

    def __str__(self):
        return f"OTP for {self.user.username if self.user.username else 'Unknown username'}"
    




class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    messages = models.JSONField()  
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Conversation {self.id} with {self.user.username}"
    
    # def delete_conversation(self):
    #     if self.timestamp + 30 < datetime.datetime.now()
    #     self.delete()

