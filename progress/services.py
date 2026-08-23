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
    TrainingSession,
    TrainingSessionQuestion,
    TrainingAnswer,
    TrainingQuestionHistory,
)
from collections import defaultdict
from django.db.models import Subquery, OuterRef, F
from content.models import Category, Subject, Skill, Concept, PlacementQuestion, TrainingQuestion

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

    concept_counts = PlacementQuestion.objects.concept_level_counts(concepts)
    counts_map = {row['concept_id']: row for row in concept_counts}

    valid_concepts = []
    for concept in concepts:
        row = counts_map.get(concept.id)
        if not row:
            continue
        if (
            row['beginner_count'] >= 2 and
            row['intermediate_count'] >= 2 and
            row['advanced_count'] >= 2
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
    profiles = UserConceptProfile.objects.filter(
        user=user,
        concept__in=valid_concepts
    )
    profiles_map = {p.concept_id: p for p in profiles}

    ordered_concepts = []
    for concept in valid_concepts:

        profile = profiles_map.get(concept.id)

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

    PLAN = {
        'beginner': 2,
        'intermediate': 2,
        'advanced': 2,
    }

    candidates = (
        PlacementQuestion.objects.filter(
            concept__in=selected_concepts,
            is_active=True,
        )
        .annotate(
            times_seen=Subquery(
                PlacementQuestionHistory.objects.filter(
                    user=user,
                    question=OuterRef('pk')
                ).values('times_seen')[:1]
            )
        )
        .order_by(
            'concept_id',
            'level',
            F('times_seen').asc(nulls_first=True),
        )
    )

    grouped = defaultdict(list)
    for q in candidates:
        grouped[(q.concept_id, q.level)].append(q)

    questions = []
    for concept in selected_concepts:
        for level, count in PLAN.items():
            selected_questions = grouped.get((concept.id, level), [])[:count]

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

    PlacementSessionQuestion.objects.bulk_create([
        PlacementSessionQuestion(session=session, question=q, order=idx)
        for idx, q in enumerate(questions)
    ])

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

def get_progress_overview(user, request):

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
            'icon': request.build_absolute_uri(category.icon.url) if category.icon else None,
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

def get_category_progress(user, category_id, request):
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
            'icon': request.build_absolute_uri(subject.icon.url) if subject.icon else None,
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
            'icon': request.build_absolute_uri(category.icon.url) if category.icon else None,
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

#_________________________________________________________________________________________________________
#___________________________________Training______________________________________________________________
#_________________________________________________________________________________________________________

XP_PER_CORRECT_ANSWER = 10

TRAINING_PLAN = {
    'beginner': 3,
    'intermediate': 4,
    'advanced': 3,
}


# ───── التحقق من جاهزية المفهوم للتدريب ─────

def get_valid_training_concepts(skill):
    concepts = Concept.objects.filter(skill=skill, is_active=True)
    valid = []
    for concept in concepts:
        qs = TrainingQuestion.objects.filter(concept=concept)
        if (
            qs.filter(level='beginner').count() >= TRAINING_PLAN['beginner'] and
            qs.filter(level='intermediate').count() >= TRAINING_PLAN['intermediate'] and
            qs.filter(level='advanced').count() >= TRAINING_PLAN['advanced']
        ):
            valid.append(concept)
    return valid


# ───── اختيار المفهوم الأضعف تلقائياً ─────

def select_auto_training_concept(user, skill):
    valid_concepts = get_valid_training_concepts(skill)
    if not valid_concepts:
        return None

    STATUS_PRIORITY = {'weak': 1, 'improving': 2, 'not_started': 3, 'strong': 4}
    ordered_concepts = []
    for concept in valid_concepts:
        profile = UserConceptProfile.objects.filter(user=user, concept=concept).first()
        status = profile.status if profile else 'not_started'
        times_trained = profile.times_trained if profile else 0

        ordered_concepts.append({
            'concept': concept,
            'priority': STATUS_PRIORITY[status],
            'times_trained': times_trained,
            'order': getattr(concept, 'order', concept.id),
        })

    ordered_concepts.sort(
        key=lambda item: (item['priority'], item['times_trained'], item['order'])
    )
    return ordered_concepts[0]['concept']


# ───── بناء جلسة التدريب ─────

def build_training_session(user, skill, mode='manual', concept=None):
    if mode == 'auto':
        concept = select_auto_training_concept(user, skill)
        if not concept:
            return None, {'reason': 'no_valid_concepts'}
    else:
        if not concept:
            return None, {'reason': 'concept_required'}
        if concept not in get_valid_training_concepts(skill):
            return None, {'reason': 'concept_not_ready'}

    questions = []
    for level, count in TRAINING_PLAN.items():
        level_qs = TrainingQuestion.objects.filter(concept=concept, level=level)
        level_qs = level_qs.order_by(
            Subquery(
                TrainingQuestionHistory.objects.filter(
                    user=user, question=OuterRef('pk')
                ).values('times_seen')[:1]
            ).asc(nulls_first=True)
        )
        selected = list(level_qs[:count])
        if len(selected) < count:
            return None, {'reason': 'not_enough_questions'}
        questions.extend(selected)

    shuffle(questions)

    session = TrainingSession.objects.create(
        user=user, skill=skill, concept=concept, mode=mode
    )
    for idx, q in enumerate(questions):
        TrainingSessionQuestion.objects.create(session=session, question=q, order=idx)

    return session, None


# ───── إرسال إجابة سؤال واحد ─────

def submit_training_answer(session, question_id, user_answer):
    session_question = session.session_questions.filter(question_id=question_id).first()
    if not session_question:
        raise ValidationError('السؤال لا ينتمي لهذه الجلسة')

    if TrainingAnswer.objects.filter(session=session, question_id=question_id).exists():
        raise ValidationError('تم الإجابة على هذا السؤال مسبقاً')

    question = session_question.question
    is_correct = question.correct_answer.strip() == (user_answer or '').strip()

    TrainingAnswer.objects.create(
        session=session,
        question=question,
        user_answer=user_answer,
        is_correct=is_correct,
    )

    # تحديث تاريخ السؤال لهذا الطالب
    history, _ = TrainingQuestionHistory.objects.get_or_create(user=session.user, question=question)
    history.times_seen += 1
    if is_correct:
        history.times_correct += 1
    history.last_result = 'correct' if is_correct else 'wrong'
    history.save()

    # الـ xp يزيد فقط عند الإجابة الصحيحة، بغض النظر عن استخدام hint
    xp_earned = 0
    if is_correct:
        xp_earned = XP_PER_CORRECT_ANSWER
        session.xp_earned += xp_earned
        session.save(update_fields=['xp_earned'])

        profile, _ = UserSkillProfile.objects.get_or_create(user=session.user, skill=session.skill)
        profile.xp_total += xp_earned
        profile.save(update_fields=['xp_total'])

    return {
        'question_id': question.id,
        'is_correct': is_correct,
        'correct_answer': question.correct_answer,
        'explanation': question.explanation,
        'xp_earned': xp_earned,
        'session_xp_total': session.xp_earned,
    }


# ───── إنهاء الجلسة ─────

def complete_training_session(session):
    if session.completed_at:
        return session.result

    total = session.session_questions.count()
    answers = session.answers.select_related('question')

    correct_count = sum(1 for a in answers if a.is_correct)
    wrong_count = total - correct_count

    answered_questions = [
        {
            'question_id': a.question.id,
            'question': a.question.question,
            'question_type': a.question.question_type,
            'level': a.question.level,
            'user_answer': a.user_answer,
            'correct_answer': a.question.correct_answer,
            'is_correct': a.is_correct,
            'explanation': a.question.explanation,
        }
        for a in answers
    ]

    wrong_questions = [
        {
            'question_id': a.question.id,
            'question': a.question.question,
            'question_type': a.question.question_type,
            'level': a.question.level,
            'user_answer': a.user_answer,
            'correct_answer': a.question.correct_answer,
            'explanation': a.question.explanation,
        }
        for a in answers if not a.is_correct
    ]

    answered_ids = {a.question_id for a in answers}
    unanswered = session.session_questions.exclude(question_id__in=answered_ids).select_related('question')

    unanswered_questions = [
        {
            'question_id': sq.question.id,
            'question': sq.question.question,
            'question_type': sq.question.question_type,
            'level': sq.question.level,
            'correct_answer': sq.question.correct_answer,
            'explanation': sq.question.explanation,
        }
        for sq in unanswered
    ]

    session.completed_at = timezone.now()
    session.result = {
        'total_questions': total,
        'answered_questions_count': answers.count(),
        'answered_questions': answered_questions,
        'correct_count': correct_count,
        'wrong_count': wrong_count,
        'xp_earned': session.xp_earned,
        'score': round(correct_count / total * 100) if total else 0,
        'wrong_questions': wrong_questions,
        'unanswered_questions': unanswered_questions,
    }
    session.save()

    return session.result