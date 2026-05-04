from django.db import models
from django.contrib.auth.models import User
from curriculum.models import Subject, Block, Topic


class PastQuestionUpload(models.Model):
    """Raw past-question file uploaded by a class rep."""
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True)
    block = models.ForeignKey(Block, on_delete=models.CASCADE, null=True, blank=True)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, null=True, blank=True)
    file_content = models.TextField()
    file_name = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.file_name or 'PQ'} by {self.uploaded_by.username} ({self.uploaded_at.date()})"
