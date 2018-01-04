from django.contrib import admin
from client.models import Engagement, LandingPage, EmailTemplate, Campaign, Client


class PageAdmin(admin.ModelAdmin):
    model = LandingPage


class EmailTemplateAdmin(admin.ModelAdmin):
    model = EmailTemplate


class EngagementAdmin(admin.ModelAdmin):
    def queryset(self, request):
        return Engagement.objects.filter(user=request.user)


admin.site.register(Engagement, EngagementAdmin)
admin.site.register(Campaign)
admin.site.register(Client)
admin.site.register(LandingPage, PageAdmin)
admin.site.register(EmailTemplate, EmailTemplateAdmin)
