from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.contrib.auth.models import User
from accounts.models import Profile, ClassGroup
from curriculum.models import Subject, Slide, Quiz, QuizAttempt
from pastquestions.models import PastQuestionUpload

@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_analytics(request):
    """
    Returns analytics data for the admin dashboard.
    Only accessible by users with is_staff or is_superuser.
    """
    try:
        total_users = User.objects.count()
        total_premium = Profile.objects.filter(subscription_tier='premium').count()
        total_classes = ClassGroup.objects.count()
        total_subjects = Subject.objects.count() if hasattr(Subject, 'objects') else 0
        total_slides = Slide.objects.count() if hasattr(Slide, 'objects') else 0
        total_quizzes = QuizAttempt.objects.count() if hasattr(QuizAttempt, 'objects') else 0
        
        from django.db.models import Sum
        from django.db.models.functions import TruncMonth
        from django.utils import timezone
        from datetime import timedelta
        
        # Real Revenue Calculation
        from accounts.models import PaymentTransaction
        
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        
        # Monthly Revenue (last 30 days)
        monthly_revenue = PaymentTransaction.objects.filter(
            status='success', 
            created_at__gte=thirty_days_ago
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Yearly Revenue (last 365 days)
        yearly_revenue = PaymentTransaction.objects.filter(
            status='success',
            created_at__gte=now - timedelta(days=365)
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return Response({
            "total_users": total_users,
            "total_premium_users": total_premium,
            "total_classes": total_classes,
            "total_subjects": total_subjects,
            "total_slides": total_slides,
            "total_quizzes_taken": total_quizzes,
            "revenue_summary": {
                "monthly": monthly_revenue,
                "yearly": yearly_revenue
            }
        })
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_users(request):
    """Returns a list of all users for the admin dashboard"""
    try:
        from accounts.serializers import ProfileSerializer
        # We fetch all profiles. A robust admin would use pagination.
        profiles = Profile.objects.select_related('user', 'school', 'class_group').all().order_by('-created_at')
        serializer = ProfileSerializer(profiles, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_curriculum(request):
    """Returns a summary of schools, classes, and subjects for the admin dashboard"""
    try:
        from accounts.serializers import SchoolSerializer, ClassGroupSerializer
        from accounts.models import School
        schools = SchoolSerializer(School.objects.all(), many=True).data if hasattr(School, 'objects') else []
        classes = ClassGroupSerializer(ClassGroup.objects.all(), many=True).data
        subjects = []
        if hasattr(Subject, 'objects'):
            subjects = [{"id": s.id, "name": s.name} for s in Subject.objects.all()]
        return Response({
            "schools": schools,
            "classes": classes,
            "subjects": subjects
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_payments(request):
    """Returns a list of all payment transactions for the admin dashboard"""
    try:
        from accounts.models import PaymentTransaction
        from accounts.serializers import PaymentTransactionSerializer
        
        # In a real app we would paginate this
        payments = PaymentTransaction.objects.select_related('user').all().order_by('-created_at')
        
        # Serialize payments, adding user info
        data = []
        for p in payments:
            data.append({
                "id": p.id,
                "reference": p.reference,
                "amount": p.amount,
                "currency": p.currency,
                "status": p.status,
                "subscription_months": p.subscription_months,
                "created_at": p.created_at,
                "verified_at": p.verified_at,
                "user": {
                    "id": p.user.id,
                    "username": p.user.username,
                    "email": p.user.email,
                    "name": p.user.get_full_name()
                }
            })
            
        return Response(data)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

