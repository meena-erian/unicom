from django.contrib import admin
from django.utils.html import format_html
from django_ace import AceWidget
from ..models import Request, RequestCategory

class RequestCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'sequence', 'is_active', 'is_public')
    list_filter = ('is_active', 'is_public', 'parent')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('allowed_channels', 'authorized_members', 'authorized_groups')
    
    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'processing_function':
            kwargs['widget'] = AceWidget(
                mode='python',
                theme='twilight',
                width="100%",
                height="300px"
            )
        return super().formfield_for_dbfield(db_field, **kwargs)
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Prevent a category from being its own parent
        if obj:
            form.base_fields['parent'].queryset = RequestCategory.objects.exclude(pk=obj.pk)
        
        # Set template code as initial value for new categories
        if not obj and 'processing_function' in form.base_fields:
            form.base_fields['processing_function'].initial = obj.get_template_code() if obj else RequestCategory().get_template_code()
        
        return form

    class Media:
        css = {
            'all': ('admin/css/forms.css',)
        }
        js = ('unicom/js/jquery.init.js', 'admin/js/core.js',)

class RequestAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'status', 'member_link', 'category', 'channel', 'created_at')
    list_display_links = ('__str__',)
    list_filter = (
        'status',
        'channel',
        'category',
        ('member', admin.RelatedOnlyFieldListFilter),
        ('created_at', admin.DateFieldListFilter),
    )
    search_fields = (
        'display_text',
        'message__text',
        'email',
        'phone',
        'member__name',
        'member__email',
        'member__phone',
        'metadata',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'pending_at',
        'identifying_at',
        'categorizing_at',
        'queued_at',
        'processing_at',
        'completed_at',
        'failed_at',
        'error',
    )
    raw_id_fields = ('message', 'account', 'member', 'category')
    date_hierarchy = 'created_at'

    def member_link(self, obj):
        if obj.member:
            url = f"/admin/unicom/member/{obj.member.id}/change/"
            return format_html('<a href="{}">{}</a>', url, obj.member.name)
        return "-"
    member_link.short_description = "Member"

    fieldsets = (
        ('Message', {
            'fields': ('message', 'display_text')
        }),
        ('Basic Information', {
            'fields': ('status', 'error', 'account', 'channel', 'member')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone')
        }),
        ('Categorization', {
            'fields': ('category',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'pending_at',
                'identifying_at',
                'categorizing_at',
                'queued_at',
                'processing_at',
                'completed_at',
                'failed_at',
            ),
            'classes': ('collapse',)
        }),
    ) 