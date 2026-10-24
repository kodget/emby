"""Atomic, repeatable class registration without granting approval privileges."""
from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import ClassGroup, ClassRole, OnboardingQuestion, OnboardingResponse, Profile, School
from .class_heads import request_review
from .email_service import send_transactional_email


@transaction.atomic
def complete_onboarding(user_id, data):
    profile = Profile.objects.select_for_update().select_related("user").get(user_id=user_id)
    role = data["class_role"]
    code = data.get("class_code", "").strip()
    if profile.onboarding_completed:
        if (profile.class_role != role or profile.set_name != data["set_name"]
                or not profile.school or profile.school.name != data["school_name"]
                or (code and (not profile.class_group or profile.class_group.code != code))):
            raise ValidationError("Onboarding is already complete. Use the class-management flow to change membership.")
        return profile, False

    responses = data.get("responses", [])
    parsed = []
    for item in responses:
        try:
            question_id = int(item["question_id"])
            answer = item["answer"]
        except (KeyError, TypeError, ValueError):
            raise ValidationError({"responses": "Each response needs a question_id and answer."}) from None
        parsed.append((question_id, answer))
    question_ids = {question_id for question_id, _ in parsed}
    if len(question_ids) != len(parsed) or OnboardingQuestion.objects.filter(
        pk__in=question_ids, is_active=True,
    ).count() != len(question_ids):
        raise ValidationError({"responses": "Use each active onboarding question at most once."})

    group = None
    if code:
        try:
            group = ClassGroup.objects.get(code=code, is_active=True)
        except ClassGroup.DoesNotExist:
            raise ValidationError({"class_code": "Invalid or inactive class code."}) from None
        school, set_name = group.school, group.set_name
    else:
        school, _ = School.objects.get_or_create(name=data["school_name"])
        set_name = data["set_name"]
        if role == ClassRole.CLASS_HEAD:
            group, _ = ClassGroup.objects.get_or_create(
                school=school, set_name=set_name,
                defaults={"code": ClassGroup.generate_code()},
            )
            if not group.is_active:
                raise ValidationError("This class is inactive. Contact an administrator.")

    profile.school = school
    profile.set_name = set_name
    profile.class_role = role
    profile.class_group = group
    profile.class_head_verified = False
    profile.class_head_verification_requested = False
    profile.class_head_rejection_reason = ""
    profile.class_capabilities = []
    profile.onboarding_completed = True
    profile.save()
    # A stale mirror membership must not confer authority after registration.
    profile.user.managed_classes.clear()
    for question_id, answer in parsed:
        OnboardingResponse.objects.update_or_create(
            user_id=user_id, question_id=question_id, defaults={"answer": answer},
        )
    if role == ClassRole.CLASS_HEAD:
        profile, _ = request_review(user_id)
        transaction.on_commit(lambda: send_transactional_email(
            "Your class code - Emby",
            f"Your class-head application for {school.name} - {set_name} is pending review.\n\n"
            f"Your class code is: {group.code}\n\n"
            "The class code does not grant class-head privileges. An administrator must approve your request.",
            [profile.user.email],
        ))
    return profile, True


@transaction.atomic
def join_student_class(user_id, code):
    profile = Profile.objects.select_for_update().get(user_id=user_id)
    group = ClassGroup.objects.get(code=code, is_active=True)
    if profile.class_group_id == group.pk:
        return group
    if profile.class_role == ClassRole.CLASS_HEAD or profile.class_head_verified:
        raise ValidationError("Class-head membership changes require administrator review.")
    # Upload privileges belong to the old class, not to knowledge of another code.
    profile.class_group = group
    profile.school = group.school
    profile.set_name = group.set_name
    profile.class_role = ClassRole.STUDENT
    profile.class_capabilities = []
    profile.class_head_verified = False
    profile.class_head_verification_requested = False
    profile.class_head_rejection_reason = ""
    profile.save()
    profile.user.managed_classes.clear()
    return group
