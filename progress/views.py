from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from content.models import Concept, Skill
from .models import PlacementSession, TrainingSession, UserConceptProfile, UserSkillProfile
from .serializers import PlacementSessionHistorySerializer, PlacementSessionSerializer, PlacementSubmitSerializer, SkillNotStartedSerializer, TrainingAnswerInputSerializer, TrainingSessionHistorySerializer, TrainingSessionSerializer, UserConceptProfileSerializer, UserSkillProfileSerializer
from .services import build_placement_session, build_training_session, calculate_and_save_result, complete_training_session, get_category_progress, get_progress_overview, reset_skill_progress, submit_training_answer
from rest_framework.exceptions import ValidationError


# ───── بدء الجلسة ─────

class StartPlacementSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, category_pk, subject_pk, skill_pk):
        skill = Skill.objects.filter(
            id=skill_pk,
            is_active=True,
            subject_id=subject_pk,
            subject__category_id=category_pk
        ).first()

        if not skill:
            return Response(
                {'detail': 'المهارة غير موجودة'},
                status=status.HTTP_404_NOT_FOUND
            )

        session, error = build_placement_session(request.user, skill)

        if error:
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        serializer = PlacementSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ───── إرسال الإجابات ─────

class SubmitPlacementSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = PlacementSession.objects.filter(
            id=session_id,
            user=request.user,
            completed_at__isnull=True
        ).first()

        if not session:
            return Response(
                {'detail': 'الجلسة غير موجودة أو منتهية'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = PlacementSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        result = calculate_and_save_result(
            session,
            serializer.validated_data['answers']
        )

        return Response(result, status=status.HTTP_200_OK)


#---------------- سجل الجلسات -------------------------

class PlacementSessionHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = PlacementSessionHistorySerializer

    def get_queryset(self):
        return PlacementSession.objects.filter(
            user=self.request.user,
            completed_at__isnull=False
        ).order_by('-started_at')
    
#------------- reset المهارة ----------------------------

class ResetSkillProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, category_pk, subject_pk, skill_pk):
        skill = Skill.objects.filter(
            id=skill_pk,
            is_active=True,
            subject_id=subject_pk,
            subject__category_id=category_pk
        ).first()

        if not skill:
            return Response(
                {'detail': 'المهارة غير موجودة'},
                status=status.HTTP_404_NOT_FOUND
            )

        reset_skill_progress(request.user, skill)
        return Response(status=status.HTTP_204_NO_CONTENT)
    

#-------------------------------------------------------

class UserSkillProfileViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSkillProfileSerializer

    def get_queryset(self):
        return UserSkillProfile.objects.filter(
            user=self.request.user
        ).select_related('skill')

    def list(self, request, *args, **kwargs):
        category_pk = kwargs.get('category_pk') or request.query_params.get('category_id')
        subject_pk  = kwargs.get('subject_pk')  or request.query_params.get('subject_id')

        all_skills_qs = Skill.objects.filter(is_active=True)
        if category_pk:
            all_skills_qs = all_skills_qs.filter(subject__category_id=category_pk)
        if subject_pk:
            all_skills_qs = all_skills_qs.filter(subject_id=subject_pk)

        profiles = self.get_queryset()
        if category_pk:
            profiles = profiles.filter(skill__subject__category_id=category_pk)
        if subject_pk:
            profiles = profiles.filter(skill__subject_id=subject_pk)

        started_skill_ids = set(profiles.values_list('skill_id', flat=True))

        not_started_skills = all_skills_qs.exclude(id__in=started_skill_ids)

        started_data     = UserSkillProfileSerializer(profiles, many=True).data
        not_started_data = SkillNotStartedSerializer(not_started_skills, many=True).data

        return Response(list(started_data) + list(not_started_data))

class UserConceptProfileViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = UserConceptProfileSerializer

    def get_queryset(self):
        queryset = UserConceptProfile.objects.filter(
            user=self.request.user
        ).select_related('concept')

        category_pk = self.kwargs.get('category_pk')
        subject_pk  = self.kwargs.get('subject_pk')
        skill_pk    = self.kwargs.get('skill_pk')

        if category_pk:
            queryset = queryset.filter(concept__skill__subject__category_id=category_pk)
        if subject_pk:
            queryset = queryset.filter(concept__skill__subject_id=subject_pk)
        if skill_pk:
            queryset = queryset.filter(concept__skill_id=skill_pk)

        return queryset
    
class ProgressOverview(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_progress_overview(request.user, request)
        return Response(data)
    
class CategoryProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, category_pk):
        data = get_category_progress(request.user, category_pk, request)
        if not data:
            return Response(
                {'detail': 'Category not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(data)
    
#_____________________________________Training______________________________________
#___________________________________________________________________________________

# ───── بدء جلسة تدريب ─────

class StartTrainingSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, category_pk, subject_pk, skill_pk):
        skill = Skill.objects.filter(
            id=skill_pk, is_active=True,
            subject_id=subject_pk, subject__category_id=category_pk
        ).first()
        if not skill:
            return Response({'detail': 'المهارة غير موجودة'}, status=status.HTTP_404_NOT_FOUND)

        mode = request.data.get('mode', 'manual')
        if mode not in ('auto', 'manual'):
            return Response({'detail': 'mode غير صحيح، استخدم auto أو manual'}, status=status.HTTP_400_BAD_REQUEST)

        concept = None
        if mode == 'manual':
            concept_id = request.data.get('concept_id')
            if not concept_id:
                return Response({'detail': 'concept_id مطلوب في الوضع اليدوي'}, status=status.HTTP_400_BAD_REQUEST)
            concept = Concept.objects.filter(id=concept_id, skill=skill, is_active=True).first()
            if not concept:
                return Response({'detail': 'المفهوم غير موجود'}, status=status.HTTP_404_NOT_FOUND)

        session, error = build_training_session(request.user, skill, mode=mode, concept=concept)
        if error:
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        serializer = TrainingSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ───── إرسال إجابة سؤال واحد ─────

class SubmitTrainingAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = TrainingSession.objects.filter(
            id=session_id, user=request.user, completed_at__isnull=True
        ).first()
        if not session:
            return Response({'detail': 'الجلسة غير موجودة أو منتهية'}, status=status.HTTP_404_NOT_FOUND)

        serializer = TrainingAnswerInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = submit_training_answer(
                session,
                serializer.validated_data['question_id'],
                serializer.validated_data['user_answer'],
            )
        except ValidationError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)


# ───── إنهاء الجلسة ─────

class CompleteTrainingSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = TrainingSession.objects.filter(
            id=session_id, user=request.user, completed_at__isnull=True
        ).first()
        if not session:
            return Response({'detail': 'الجلسة غير موجودة أو منتهية بالفعل'}, status=status.HTTP_404_NOT_FOUND)

        result = complete_training_session(session)
        return Response(result, status=status.HTTP_200_OK)


# ───── سجل جلسات التدريب ─────

class TrainingSessionHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = TrainingSessionHistorySerializer

    def get_queryset(self):
        return TrainingSession.objects.filter(
            user=self.request.user, completed_at__isnull=False
        ).order_by('-started_at')