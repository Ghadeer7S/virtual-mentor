# from django.contrib import admin
# from .models import Category, Subject, Skill, PlacementQuestion


# class SubjectInline(admin.TabularInline):
#     model = Subject
#     extra = 1


# class SkillInline(admin.TabularInline):
#     model = Skill
#     extra = 1


# class PlacementQuestionInline(admin.TabularInline):
#     model = PlacementQuestion
#     extra = 1


# @admin.register(Category)
# class CategoryAdmin(admin.ModelAdmin):
#     list_display = ['name', 'is_active', 'order']
#     inlines = [SubjectInline]


# @admin.register(Subject)
# class SubjectAdmin(admin.ModelAdmin):
#     list_display = ['name', 'category', 'is_active', 'order']
#     inlines = [SkillInline]


# @admin.register(Skill)
# class SkillAdmin(admin.ModelAdmin):
#     list_display = ['name', 'subject', 'is_active', 'order', 'created_by']
#     inlines = [PlacementQuestionInline]


# @admin.register(PlacementQuestion)
# class PlacementQuestionAdmin(admin.ModelAdmin):
#     list_display = ['concept', 'skill', 'level', 'question_type', 'order']