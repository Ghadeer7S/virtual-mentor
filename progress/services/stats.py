"""Progress statistics for the dashboard/student overview.

Both endpoints crawl the same per-scope numbers, so a single in-memory
summary engine is reused and all aggregation happens with a handful of
batched queries instead of a query storm per category/subject.
"""

from collections import defaultdict

from django.db.models import Count
from django.utils import timezone

from content.models import Category, Concept, Skill, Subject

from ..constants import LEVEL_VALUES, SKILL_IMPROVING_SCORE
from ..models import UserSkillProfile


# ────────────────────────────── shared summaries ─────────────────────────────

def _summarize(profiles, total_skills):
    """Reduce a (preloaded) list of profiles into the shared stat block."""
    mastered = sum(1 for p in profiles if p.is_mastered)
    improving = sum(
        1 for p in profiles
        if not p.is_mastered and p.assessment_score >= SKILL_IMPROVING_SCORE
    )
    weak = sum(
        1 for p in profiles
        if not p.is_mastered
        and p.assessment_score < SKILL_IMPROVING_SCORE
        and p.total_assessments > 0
    )

    scores = [p.assessment_score for p in profiles]
    dates = [p.last_assessed_at for p in profiles if p.last_assessed_at]

    return {
        'mastered_skills': mastered,
        'improving_skills': improving,
        'weak_skills': weak,
        'not_started_skills': total_skills - len(profiles),
        'progress_percentage': (
            round(mastered / total_skills * 100, 2) if total_skills else 0
        ),
        'average_score': round(sum(scores) / len(profiles), 1) if profiles else 0,
        'total_xp': sum(p.xp_total for p in profiles),
        'last_activity': max(dates) if dates else None,
    }


def _quick_stats(profiles, *, include_levels=False, include_subject=False):
    if not profiles:
        return None

    now = timezone.now()
    weakest = min(profiles, key=lambda p: p.assessment_score)
    strongest = max(profiles, key=lambda p: p.assessment_score)
    available = sum(
        1 for p in profiles
        if p.can_reassess_at and p.can_reassess_at <= now
    )

    def skill_entry(profile, with_subject):
        entry = {
            'name': profile.skill.name,
            'score': profile.assessment_score,
        }
        if with_subject:
            entry['subject'] = profile.skill.subject.name
        else:
            entry['id'] = profile.skill.id
            entry['level'] = profile.current_level
        return entry

    stats = {
        'weakest_skill': skill_entry(weakest, include_subject),
        'strongest_skill': skill_entry(strongest, include_subject),
        'next_assessment_available': available,
    }
    if include_levels:
        stats['skills_by_level'] = {
            level: sum(1 for p in profiles if p.current_level == level)
            for level in LEVEL_VALUES
        }
    return stats


def _recent_activity(profiles, last_activity):
    if not last_activity:
        return None
    last_profile = max(
        (p for p in profiles if p.last_assessed_at),
        key=lambda p: p.last_assessed_at,
    )
    return {
        'last_skill_assessed': last_profile.skill.name,
        'last_assessment_date': last_activity,
    }


def _absolute_uri(request, image_field):
    if image_field is None:
        return None
    return request.build_absolute_uri(image_field.url)


# ────────────────────────────── overview endpoint ────────────────────────────

def get_progress_overview(user, request):
    categories = list(Category.objects.filter(is_active=True))
    category_ids = [c.id for c in categories]

    subject_counts = {
        category_id: total
        for category_id, total in Subject.objects.filter(
            category_id__in=category_ids,
            is_active=True,
        ).values_list('category_id').annotate(total=Count('id'))
    }

    skills_by_category = defaultdict(list)
    for category_id, skill_id in Skill.objects.filter(
        subject__category_id__in=category_ids,
        is_active=True,
    ).values_list('subject__category_id', 'id'):
        skills_by_category[category_id].append(skill_id)

    concepts_by_category = {
        category_id: total
        for category_id, total in Concept.objects.filter(
            skill__subject__category_id__in=category_ids,
            is_active=True,
        ).values_list('skill__subject__category_id').annotate(total=Count('id'))
    }

    profiles_by_category = defaultdict(list)
    for profile in UserSkillProfile.objects.filter(
        user=user,
        skill__subject__category_id__in=category_ids,
        skill__is_active=True,
    ).select_related('skill', 'skill__subject'):
        profiles_by_category[profile.skill.subject.category_id].append(profile)

    result = []
    for category in categories:
        profiles = profiles_by_category.get(category.id, [])
        skill_ids = skills_by_category.get(category.id, [])
        stats = _summarize(profiles, len(skill_ids))

        result.append({
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'icon': _absolute_uri(request, category.icon),
            'stats': {
                'total_subjects': subject_counts.get(category.id, 0),
                'total_skills': len(skill_ids),
                'total_concepts': concepts_by_category.get(category.id, 0),
                **stats,
            },
            'quick_stats': _quick_stats(profiles, include_subject=True),
        })

    return {
        'total_categories': len(result),
        'categories': result,
    }


# ─────────────────────────── category progress endpoint ──────────────────────

def get_category_progress(user, category_id, request):
    category = Category.objects.filter(id=category_id, is_active=True).first()
    if not category:
        return None

    subjects = list(Subject.objects.filter(category=category, is_active=True))
    subject_ids = [s.id for s in subjects]

    skills_by_subject = defaultdict(list)
    for subject_id, skill_id in Skill.objects.filter(
        subject_id__in=subject_ids,
        is_active=True,
    ).values_list('subject_id', 'id'):
        skills_by_subject[subject_id].append(skill_id)

    concepts_by_subject = {
        subject_id: total
        for subject_id, total in Concept.objects.filter(
            skill__subject_id__in=subject_ids,
            is_active=True,
        ).values_list('skill__subject_id').annotate(total=Count('id'))
    }

    profiles_by_subject = defaultdict(list)
    for profile in UserSkillProfile.objects.filter(
        user=user,
        skill__subject_id__in=subject_ids,
    ).select_related('skill'):
        profiles_by_subject[profile.skill.subject_id].append(profile)

    now = timezone.now()
    summary_mastered = 0
    summary_total = 0
    summary_xp = 0
    completed_subjects = 0
    in_progress_subjects = 0
    not_started_subjects = 0

    subjects_data = []
    for subject in subjects:
        profiles = profiles_by_subject.get(subject.id, [])
        skill_ids = skills_by_subject.get(subject.id, [])
        total_skills = len(skill_ids)
        stats = _summarize(profiles, total_skills)

        last_activity = stats['last_activity']
        days_since = (now - last_activity).days if last_activity else None

        if not profiles:
            status = 'not_started'
        elif stats['mastered_skills'] == total_skills:
            status = 'completed'
        else:
            status = 'in_progress'

        subjects_data.append({
            'id': subject.id,
            'name': subject.name,
            'description': subject.description,
            'icon': _absolute_uri(request, subject.icon),
            'stats': {
                'total_skills': total_skills,
                'total_concepts': concepts_by_subject.get(subject.id, 0),
                **stats,
                'days_since_last_activity': days_since,
            },
            'quick_stats': _quick_stats(profiles, include_levels=True),
            'recent_activity': _recent_activity(profiles, last_activity),
            'status': status,
        })

        summary_mastered += stats['mastered_skills']
        summary_total += total_skills
        summary_xp += stats['total_xp']
        if status == 'completed':
            completed_subjects += 1
        elif status == 'in_progress':
            in_progress_subjects += 1
        else:
            not_started_subjects += 1

    overall_progress = (
        round(summary_mastered / summary_total * 100, 2) if summary_total else 0
    )

    return {
        'specialization': {
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'icon': _absolute_uri(request, category.icon),
            'total_subjects': len(subjects),
        },
        'subjects': subjects_data,
        'summary': {
            'total_subjects': len(subjects),
            'completed_subjects': completed_subjects,
            'in_progress_subjects': in_progress_subjects,
            'not_started_subjects': not_started_subjects,
            'overall_progress': overall_progress,
            'total_skills': summary_total,
            'mastered_skills': summary_mastered,
            'total_xp': summary_xp,
        },
    }