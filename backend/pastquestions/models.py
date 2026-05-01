from django.db import models
from django.contrib.auth.models import User

class Block(models.Model):
    name = models.CharField(max_length=100)
    subject = models.CharField(max_length=50)

class Topic(models.Model):
    name = models.CharField(max_length=100)
    block = models.ForeignKey(Block, on_delete=models.CASCADE)

class PastQuestionUpload(models.Model):

    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE) # class_rep username
    block = models.ForeignKey(Block, on_delete=models.CASCADE)
    file_content = models.TextField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

class GeneratedMCQ(models.Model):
    question = models.TextField()
    options = models.JSONField()
    correct = models.IntegerField()
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)

class GeneratedEssay(models.Model):
    question = models.TextField()
    model_answer = models.TextField()
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
class Meta:
    ordering = ['-id']