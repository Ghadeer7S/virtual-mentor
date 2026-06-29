from random import shuffle
from django.utils import timezone
from datetime import timedelta

from rest_framework.exceptions import ValidationError
from .models import (
    PlacementSession,
    PlacementSessionQuestion,
    PlacementAnswer,
    PlacementQuestionHistory,
    UserSkillProfile,
    UserConceptProfile,
)
from django.db.models import Subquery, OuterRef
from content.models import Category, Subject, Skill, Concept, PlacementQuestion

# ───── بناء الجلسة ─────

def build_placement_session(user, skill):

    # التحقق من cooldown
    profile = UserSkillProfile.objects.filter(user=user, skill=skill).first()
    if profile and profile.can_reassess_at:
        if timezone.now() < profile.can_reassess_at:
            remaining = profile.can_reassess_at - timezone.now()
            hours = int(remaining.total_seconds() // 3600)
            return None, {
                'reason': 'too_soon',
                'hours_remaining': hours,
                'can_reassess_at': profile.can_reassess_at,
            }

    
    concepts = Concept.objects.filter(skill=skill, is_active=True)
    valid_concepts = []

    for concept in concepts:
        qs = PlacementQuestion.objects.filter(
            concept=concept,
            is_active=True
        )

        beginner_count = qs.filter(level='beginner').count()
        intermediate_count = qs.filter(level='intermediate').count()
        advanced_count = qs.filter(level='advanced').count()

        if (
            beginner_count >= 2 and
            intermediate_count >= 2 and
            advanced_count >= 2
        ):
            valid_concepts.append(concept)
    #----------------
    if len(valid_concepts) < 3:
        return None, {
            'reason': 'not_enough_complete_concepts'
        }
    
    STATUS_PRIORITY = {
        'weak': 1,
        'improving': 2,
        'not_started': 3,
        'strong': 4,
    }
    ordered_concepts = []
    for concept in valid_concepts:

        profile = UserConceptProfile.objects.filter(
            user=user,
            concept=concept
        ).first()

        status = profile.status if profile else 'not_started'

        times_trained = profile.times_trained if profile else 0

        ordered_concepts.append({
            'concept': concept,
            'priority': STATUS_PRIORITY[status],
            'times_trained': times_trained,
            'order': getattr(concept, 'order', concept.id),
        })
    ordered_concepts.sort(
    key=lambda item: (
        item['priority'],
        item['times_trained'],
        item['order'],
        )
    )
    selected_concepts = [
        item['concept']
        for item in ordered_concepts[:3]
    ]


    # اختيار الأسئلة
    questions = []
    PLAN = {
        'beginner': 2,
        'intermediate': 2,
        'advanced': 2,
    }

    for concept in selected_concepts:

        qs = PlacementQuestion.objects.filter(
            concept=concept,
            is_active=True
        )

        for level, count in PLAN.items():

            level_qs = qs.filter(level=level)

            level_qs = level_qs.order_by(
                Subquery(
                    PlacementQuestionHistory.objects.filter(
                        user=user,
                        question=OuterRef('pk')
                    ).values('times_seen')[:1]
                ).asc(nulls_first=True)
            )

            selected_questions = list(level_qs[:count])

            if len(selected_questions) < count:
                return None, {
                    'reason': 'not_enough_questions'
                }

            questions.extend(selected_questions)

    if not questions:
        return None, {
            'reason': 'no_questions'
        }

    shuffle(questions)

    # إنشاء الجلسة
    session = PlacementSession.objects.create(
        user=user,
        skill=skill
    )

    for idx, q in enumerate(questions):
        PlacementSessionQuestion.objects.create(
            session=session,
            question=q,
            order=idx,
        )

    return session, None


# ───── حساب النتيجة ─────

def calculate_and_save_result(session, answers_data):
    """
    answers_data: list of dicts
    [{'question_id': 1, 'user_answer': 'x'}, ...]
    """
    session_question_ids = set(
        session.session_questions.values_list(
            'question_id',
            flat=True
        )
    )

    for item in answers_data:
        if item['question_id'] not in session_question_ids:
            raise ValidationError(
                f"Question {item['question_id']} does not belong to this session"
            )
    
    answered_ids = {item['question_id'] for item in answers_data}
    session_question_ids = session.session_questions.values_list('question_id', flat=True)
    for qid in session_question_ids:
        if qid not in answered_ids:
            answers_data.append({
                'question_id': qid,
                'user_answer': '',
            })

    # حفظ الإجابات
    for item in answers_data:
        question = PlacementQuestion.objects.get(id=item['question_id'])
        is_correct = question.correct_answer == item['user_answer']

        PlacementAnswer.objects.create(
            session=session,
            question=question,
            user_answer=item['user_answer'],
            is_correct=is_correct,
        )

        # تحديث PlacementQuestionHistory
        history, _ = PlacementQuestionHistory.objects.get_or_create(
            user=session.user,
            question=question,
        )
        history.times_seen += 1
        if is_correct:
            history.times_correct += 1
        history.last_result = 'correct' if is_correct else 'wrong'
        history.save()

    # جلب الإجابات للحساب
    answers = session.answers.select_related(
        'question', 'question__concept'
    ).all()

    by_diff = {'beginner': [], 'intermediate': [], 'advanced': []}
    by_concept = {}

    for ans in answers:
        by_diff[ans.question.level].append(ans.is_correct)

        cid = ans.question.concept_id
        if cid not in by_concept:
            by_concept[cid] = []
        by_concept[cid].append(ans.is_correct)

    def pct(lst):
        return round(sum(lst) / len(lst) * 100) if lst else 0

    b_score = pct(by_diff['beginner'])
    i_score = pct(by_diff['intermediate'])
    a_score = pct(by_diff['advanced'])

    # تحديد المستوى
    if b_score >= 80 and i_score >= 60:
        level = 'advanced'
    elif b_score >= 60:
        level = 'intermediate'
    else:
        level = 'beginner'

    total_correct = sum(a.is_correct for a in answers)
    total = answers.count()
    score = round(total_correct / total * 100) if total else 0

    weak_concepts = list(
        Concept.objects.filter(
            id__in=[cid for cid, lst in by_concept.items() if pct(lst) < 60]
        ).values('id', 'name')
    )

    # حفظ نتيجة الجلسة
    session.score        = score
    session.level_result = level
    session.completed_at = timezone.now()
    session.save()

    # تحديث UserSkillProfile
    profile, _ = UserSkillProfile.objects.get_or_create(
        user=session.user,
        skill=session.skill,
    )

    if profile.assessment_score:
        new_score = (profile.assessment_score * 0.7) + (score * 0.3)
    else:
        new_score = score

    profile.current_level     = level
    profile.assessment_score  = new_score
    profile.total_assessments += 1
    profile.last_assessed_at  = timezone.now()
    profile.can_reassess_at   = timezone.now() + timedelta(minutes=1)
    profile.xp_total          += score

    # تحقق من الإتقان
    if (level == 'advanced' and new_score >= 85
            and not weak_concepts
            and profile.total_assessments >= 3):
        profile.is_mastered = True
        profile.mastered_at = timezone.now()

    profile.save()

    # تحديث UserConceptProfile
    for cid, results in by_concept.items():
        concept_score = pct(results)
        cp, _ = UserConceptProfile.objects.get_or_create(
            user=session.user,
            concept_id=cid,
        )

        if cp.avg_score:
            new_avg = (cp.avg_score * 0.7) + (concept_score * 0.3)
        else:
            new_avg = concept_score

        cp.avg_score = new_avg
        cp.times_trained += 1

        if new_avg >= 70:
            cp.status = 'strong'
        elif new_avg >= 50:
            cp.status = 'improving'
        else:
            cp.status = 'weak'

        cp.save()

    result = {
        'score':         score,
        'level':         level,
        'correct_count': total_correct,
        'total_count':   total,
        'by_difficulty': {
            'beginner':     {'correct': sum(by_diff['beginner']),     'total': len(by_diff['beginner']),     'score': b_score},
            'intermediate': {'correct': sum(by_diff['intermediate']), 'total': len(by_diff['intermediate']), 'score': i_score},
            'advanced':     {'correct': sum(by_diff['advanced']),     'total': len(by_diff['advanced']),     'score': a_score},
        },
        'by_concept': [
            {
                'concept_id': cid,
                'concept_name': answers.filter(question__concept_id=cid).first().question.concept.name,
                'score':      pct(lst),
                'status':     'strong' if pct(lst) >= 70 else 'improving' if pct(lst) >= 50 else 'weak',
            }
            for cid, lst in by_concept.items()
        ],
        'weak_concepts':   weak_concepts,
        'can_reassess_at': profile.can_reassess_at.isoformat(),
        'xp_earned':       score,
        'questions_review': [
            {
                'question_id':    ans.question.id,
                'question':       ans.question.question,
                'user_answer':    ans.user_answer,
                'correct_answer': ans.question.correct_answer,
                'is_correct':     ans.is_correct,
                'level_question': ans.question.level,
                'concept_name':   ans.question.concept.name,
            }
            for ans in answers
        ],
    }

    session.result = result
    session.save()

    return result



def reset_skill_progress(user, skill):
    # حذف الجلسات وما يتبعها تلقائياً
    PlacementSession.objects.filter(user=user, skill=skill).delete()
    
    # حذف تاريخ الأسئلة
    PlacementQuestionHistory.objects.filter(
        user=user,
        question__skill=skill
    ).delete()
    
    # حذف ملف المهارة
    UserSkillProfile.objects.filter(user=user, skill=skill).delete()
    
    # حذف ملف المفاهيم المرتبطة بهذه المهارة
    UserConceptProfile.objects.filter(
        user=user,
        concept__skill=skill
    ).delete()

#-----------------------------------------------احصائيات عامة لكل التخصصات-------------------------------------------------------------------------------

def get_progress_overview(user):

    categories = Category.objects.filter(is_active=True)
    result = []

    for category in categories:
        # جلب الأرقام الكلية
        total_subjects = Subject.objects.filter(
            category=category, is_active=True
        ).count()

        skill_ids = Skill.objects.filter(
            subject__category=category, is_active=True
        ).values_list('id', flat=True)

        total_skills = len(skill_ids)

        total_concepts = Concept.objects.filter(
            skill__subject__category=category, is_active=True
        ).count()

        # جلب profiles الخاصة بهذه الـ category
        profiles = UserSkillProfile.objects.filter(
            user=user,
            skill__subject__category=category,
            skill__is_active=True,
        ).select_related('skill', 'skill__subject')

        mastered_skills    = profiles.filter(is_mastered=True).count()
        improving_skills   = profiles.filter(is_mastered=False, assessment_score__gte=50).count()
        weak_skills        = profiles.filter(is_mastered=False, assessment_score__lt=50, total_assessments__gt=0).count()
        not_started_skills = total_skills - profiles.count()

        scores     = [p.assessment_score for p in profiles]
        xp_list    = [p.xp_total for p in profiles]
        dates      = [p.last_assessed_at for p in profiles if p.last_assessed_at]

        average_score = round(sum(scores) / len(scores), 1) if scores else 0
        total_xp      = sum(xp_list)
        last_activity = max(dates) if dates else None

        progress_percentage = round((mastered_skills / total_skills) * 100, 2) if total_skills else 0

        # quick_stats
        quick_stats = None
        if profiles.exists():
            weakest   = profiles.order_by('assessment_score').first()
            strongest = profiles.order_by('-assessment_score').first()
            available = profiles.filter(can_reassess_at__lte=timezone.now()).count()

            quick_stats = {
                'weakest_skill': {
                    'name':    weakest.skill.name,
                    'score':   weakest.assessment_score,
                    'subject': weakest.skill.subject.name,
                },
                'strongest_skill': {
                    'name':    strongest.skill.name,
                    'score':   strongest.assessment_score,
                    'subject': strongest.skill.subject.name,
                },
                'next_assessment_available': available,
            }

        result.append({
            'id':          category.id,
            'name':        category.name,
            'description': category.description,
            'icon':        category.icon,
            'stats': {
                'total_subjects':    total_subjects,
                'total_skills':      total_skills,
                'total_concepts':    total_concepts,
                'mastered_skills':   mastered_skills,
                'improving_skills':  improving_skills,
                'weak_skills':       weak_skills,
                'not_started_skills': not_started_skills,
                'progress_percentage': progress_percentage,
                'average_score':     average_score,
                'total_xp':          total_xp,
                'last_activity':     last_activity,
            },
            'quick_stats': quick_stats,
        })

    return {
        'total_categories': len(result),
        'categories':       result,
    }

#_______________________________احصائيات خاصة بالتخصص_________________________________________________________________
#_____________________________________________________________________________________________________________________

def get_category_progress(user, category_id):
    from content.models import Category, Subject, Skill, Concept
    from django.utils import timezone
    from datetime import timedelta

    category = Category.objects.filter(id=category_id, is_active=True).first()
    if not category:
        return None

    subjects = Subject.objects.filter(category=category, is_active=True)
    total_subjects = subjects.count()

    subjects_data = []
    
    # summary counters
    summary_mastered   = 0
    summary_total      = 0
    summary_xp         = 0
    completed_subjects = 0
    in_progress_subjects = 0
    not_started_subjects = 0

    for subject in subjects:
        skill_ids = Skill.objects.filter(
            subject=subject, is_active=True
        ).values_list('id', flat=True)

        total_skills   = len(skill_ids)
        total_concepts = Concept.objects.filter(
            skill__in=skill_ids, is_active=True
        ).count()

        profiles = UserSkillProfile.objects.filter(
            user=user,
            skill__in=skill_ids,
        ).select_related('skill')

        mastered_skills    = profiles.filter(is_mastered=True).count()
        improving_skills   = profiles.filter(is_mastered=False, assessment_score__gte=50).count()
        weak_skills        = profiles.filter(is_mastered=False, assessment_score__lt=50, total_assessments__gt=0).count()
        not_started_skills = total_skills - profiles.count()

        scores  = [p.assessment_score for p in profiles]
        xp_list = [p.xp_total for p in profiles]
        dates   = [p.last_assessed_at for p in profiles if p.last_assessed_at]

        average_score       = round(sum(scores) / len(scores), 1) if scores else 0
        total_xp            = sum(xp_list)
        last_activity       = max(dates) if dates else None
        progress_percentage = round((mastered_skills / total_skills) * 100, 2) if total_skills else 0

        days_since = None
        if last_activity:
            days_since = (timezone.now() - last_activity).days

        # status
        if not profiles.exists():
            status = 'not_started'
        elif mastered_skills == total_skills:
            status = 'completed'
        else:
            status = 'in_progress'

        # quick_stats
        quick_stats = None
        if profiles.exists():
            weakest   = profiles.order_by('assessment_score').first()
            strongest = profiles.order_by('-assessment_score').first()
            available = profiles.filter(can_reassess_at__lte=timezone.now()).count()

            skills_by_level = {
                'beginner':     profiles.filter(current_level='beginner').count(),
                'intermediate': profiles.filter(current_level='intermediate').count(),
                'advanced':     profiles.filter(current_level='advanced').count(),
            }

            quick_stats = {
                'weakest_skill': {
                    'id':    weakest.skill.id,
                    'name':  weakest.skill.name,
                    'score': weakest.assessment_score,
                    'level': weakest.current_level,
                },
                'strongest_skill': {
                    'id':    strongest.skill.id,
                    'name':  strongest.skill.name,
                    'score': strongest.assessment_score,
                    'level': strongest.current_level,
                },
                'skills_by_level':          skills_by_level,
                'next_assessment_available': available,
            }

        # recent_activity
        recent_activity = None
        if last_activity:
            last_profile = profiles.order_by('-last_assessed_at').first()
            recent_activity = {
                'last_skill_assessed':  last_profile.skill.name,
                'last_assessment_date': last_activity,
            }

        subjects_data.append({
            'id':          subject.id,
            'name':        subject.name,
            'description': subject.description,
            'stats': {
                'total_skills':        total_skills,
                'total_concepts':      total_concepts,
                'mastered_skills':     mastered_skills,
                'improving_skills':    improving_skills,
                'weak_skills':         weak_skills,
                'not_started_skills':  not_started_skills,
                'progress_percentage': progress_percentage,
                'average_score':       average_score,
                'total_xp':            total_xp,
                'last_activity':       last_activity,
                'days_since_last_activity': days_since,
            },
            'quick_stats':     quick_stats,
            'recent_activity': recent_activity,
            'status':          status,
        })

        # summary counters
        summary_mastered += mastered_skills
        summary_total    += total_skills
        summary_xp       += total_xp

        if status == 'completed':
            completed_subjects += 1
        elif status == 'in_progress':
            in_progress_subjects += 1
        else:
            not_started_subjects += 1

    overall_progress = round((summary_mastered / summary_total) * 100, 2) if summary_total else 0

    return {
        'specialization': {
            'id':           category.id,
            'name':         category.name,
            'description':  category.description,
            'icon':         category.icon,
            'total_subjects': total_subjects,
        },
        'subjects': subjects_data,
        'summary': {
            'total_subjects':      total_subjects,
            'completed_subjects':  completed_subjects,
            'in_progress_subjects': in_progress_subjects,
            'not_started_subjects': not_started_subjects,
            'overall_progress':    overall_progress,
            'total_skills':        summary_total,
            'mastered_skills':     summary_mastered,
            'total_xp':            summary_xp,
        },
    }