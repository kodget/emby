from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import (
    Profile, School, ClassGroup, OnboardingQuestion, 
    OnboardingResponse, Announcement, PaymentTransaction, ExamCountdown
)


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ['id', 'name']


class ClassGroupSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)
    class_heads = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = ClassGroup
        fields = ['id', 'code', 'school', 'school_name', 'set_name', 
                  'class_heads', 'member_count', 'created_at']
        read_only_fields = ['code']

    def get_class_heads(self, obj):
        return [{
            'id': head.id,
            'name': head.get_full_name(),
            'email': head.email
        } for head in obj.class_heads.all()]
    
    def get_member_count(self, obj):
        return obj.members.count()


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    school_name = serializers.CharField(source='school.name', read_only=True)
    class_code = serializers.CharField(source='class_group.code', read_only=True)
    is_premium = serializers.BooleanField(read_only=True)
    can_access_app = serializers.BooleanField(read_only=True)

    class Meta:
        model = Profile
        fields = ['id', 'username', 'email', 'full_name', 'photo_url', 'role',
                  'school', 'school_name', 'set_name', 'class_group', 'class_code',
                  'subscription_tier', 'subscription_expires_at', 'is_premium',
                  'onboarding_completed', 'email_verified', 'class_head_verified',
                  'class_head_verification_requested', 'class_head_rejection_reason',
                  'can_access_app', 'streak', 'created_at']
        read_only_fields = ['subscription_tier', 'subscription_expires_at', 'email_verified',
                            'class_head_verified', 'class_head_verification_requested']


class UpdateProfileSerializer(serializers.Serializer):
    """Serializer for updating user profile"""
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    photo_url = serializers.URLField(required=False, allow_blank=True)

    def validate_first_name(self, value):
        if value and not value.strip():
            raise serializers.ValidationError("First name cannot be empty.")
        return value.strip() if value else value

    def validate_last_name(self, value):
        if value is not None:
            return value.strip()
        return value


class SignupSerializer(serializers.Serializer):
    """Email/password signup"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name']
        )
        return user


class LoginSerializer(serializers.Serializer):
    """Email/password login"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class GoogleAuthSerializer(serializers.Serializer):
    """Google OAuth"""
    token = serializers.CharField()


class OnboardingQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingQuestion
        fields = ['id', 'question_text', 'question_type', 'options', 'order']


class OnboardingResponseSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.question_text', read_only=True)

    class Meta:
        model = OnboardingResponse
        fields = ['id', 'question', 'question_text', 'answer', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class OnboardingSubmitSerializer(serializers.Serializer):
    """Submit all onboarding data at once"""
    role = serializers.ChoiceField(choices=['student', 'brainstormer', 'class_head', 'material_uploader'])
    school_name = serializers.CharField(max_length=200)
    set_name = serializers.CharField(max_length=100)
    class_code = serializers.CharField(max_length=6, required=False, allow_blank=True)
    subscription_tier = serializers.ChoiceField(choices=['free', 'premium'])
    responses = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField()),
        required=False
    )

    def validate_class_code(self, value):
        """Validate class code if provided"""
        if value and value.strip():
            code = value.strip().upper()
            if not ClassGroup.objects.filter(code=code, is_active=True).exists():
                raise serializers.ValidationError("Invalid class code.")
            return code
        return value


class JoinClassSerializer(serializers.Serializer):
    """Join class with code"""
    class_code = serializers.CharField(max_length=6)

    def validate_class_code(self, value):
        if not ClassGroup.objects.filter(code=value, is_active=True).exists():
            raise serializers.ValidationError("Invalid or inactive class code.")
        return value


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    class_code = serializers.CharField(source='class_group.code', read_only=True)
    is_class_head = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ['id', 'class_group', 'class_code', 'created_by', 'created_by_name',
                  'is_class_head', 'title', 'content', 'created_at', 'updated_at']
        read_only_fields = ['created_by', 'created_at', 'updated_at']
    
    def get_is_class_head(self, obj):
        return obj.class_group.is_class_head(obj.created_by)


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = ['id', 'reference', 'amount', 'currency', 'status',
                  'subscription_months', 'created_at', 'verified_at']
        read_only_fields = ['status', 'verified_at']


class ExamCountdownSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    class_code = serializers.CharField(source='class_group.code', read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = ExamCountdown
        fields = ['id', 'class_group', 'class_code', 'created_by', 'created_by_name',
                  'title', 'exam_date', 'exam_time', 'description', 'subject',
                  'days_remaining', 'created_at', 'updated_at']
        read_only_fields = ['created_by', 'created_at', 'updated_at']
