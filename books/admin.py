from django.contrib import admin
from .models import FlipBook, BookView, Event, FlipBookAccess, UserProfile
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.urls import path
from django import forms
from django.utils.html import format_html
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'color_preview', 'icon', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'color_preview']
    
    fieldsets = (
        ('Event Information', {
            'fields': ('name', 'description', 'icon', 'color', 'color_preview')
        }),
        ('Settings', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def color_preview(self, obj):
        return f'<div style="width: 50px; height: 50px; background-color: {obj.color}; border-radius: 8px; border: 2px solid #ddd; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"></div>'
    color_preview.short_description = 'Color Preview'
    color_preview.allow_tags = True


@admin.register(FlipBook)
class FlipBookAdmin(admin.ModelAdmin):
    list_display = ['title', 'event', 'thumbnail_preview', 'created_by', 'total_pages', 'is_published', 'created_at']
    list_filter = ['is_published', 'event', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['total_pages', 'thumbnail_preview', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Book Information', {
            'fields': ('title', 'description', 'event', 'pdf_file', 'thumbnail', 'thumbnail_preview')
        }),
        ('Settings', {
            'fields': ('is_published', 'created_by')
        }),
        ('Metadata', {
            'fields': ('total_pages', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return f'<img src="{obj.thumbnail.url}" style="max-width: 200px; max-height: 200px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />'
        return '<span style="color: #999;">No thumbnail</span>'
    thumbnail_preview.short_description = 'Thumbnail Preview'
    thumbnail_preview.allow_tags = True

    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "created_by":
            kwargs["queryset"] = User.objects.filter(is_staff=True)
            return forms.ModelChoiceField(queryset=kwargs["queryset"])
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(BookView)
class BookViewAdmin(admin.ModelAdmin):
    list_display = ['book', 'user', 'ip_address', 'viewed_at']
    list_filter = ['viewed_at']
    search_fields = ['book__title', 'ip_address']
    readonly_fields = ['book', 'user', 'ip_address', 'viewed_at']


class GrantFlipBookAccessForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.all(), label="User")
    flipbook = forms.ModelChoiceField(queryset=FlipBook.objects.all(), label="FlipBook")


def grant_flipbook_access_view(request, admin_site):
    if request.method == 'POST':
        form = GrantFlipBookAccessForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            flipbook = form.cleaned_data['flipbook']
            from .models import FlipBookAccess
            obj, created = FlipBookAccess.objects.get_or_create(user=user, flipbook=flipbook)
            if created:
                admin_site.message_user(request, f"Access granted to {user.username} for {flipbook.title}.")
            else:
                admin_site.message_user(request, f"{user.username} already has access to {flipbook.title}.")
            return redirect('..')
    else:
        form = GrantFlipBookAccessForm()
    return render(request, 'admin/grant_flipbook_access.html', {'form': form})

class FlipBookAccessAdmin(admin.ModelAdmin):
    list_display = ['user', 'flipbook', 'granted_at', 'user_email', 'user_status']
    list_filter = ['user', 'flipbook', 'granted_at']
    search_fields = ['user__username', 'user__email', 'flipbook__title']
    readonly_fields = ['granted_at', 'user_info']
    actions = []
    change_list_template = None

    fieldsets = (
        ('Access Information', {
            'fields': ('user', 'flipbook', 'granted_at')
        }),
        ('User Details', {
            'fields': ('user_info',),
            'classes': ('collapse',)
        }),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'

    def user_status(self, obj):
        if obj.user.is_active:
            return '<span style="color: green; font-weight: bold;">Active</span>'
        return '<span style="color: red; font-weight: bold;">Inactive</span>'
    user_status.short_description = 'Status'
    user_status.allow_tags = True

    def user_info(self, obj):
        user = obj.user
        info = f"""
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px;">
            <p><strong>Username:</strong> {user.username}</p>
            <p><strong>Phone Number:</strong> {getattr(user.profile, 'mobile_number', 'N/A')}</p>
            <p><strong>Full Name:</strong> {user.get_full_name() or 'N/A'}</p>
            <p><strong>Active:</strong> {'Yes' if user.is_active else 'No'}</p>
            <p><strong>Staff Member:</strong> {'Yes' if user.is_staff else 'No'}</p>
            <p><strong>Joined:</strong> {user.date_joined.strftime('%B %d, %Y')}</p>
            <p><strong>Last Login:</strong> {user.last_login.strftime('%B %d, %Y %H:%M') if user.last_login else 'Never'}</p>
        </div>
        """
        return info
    user_info.short_description = 'User Information'
    user_info.allow_tags = True

    def show_user_details(self, request, queryset):
        self.message_user(request, f"Showing details for {queryset.count()} user(s)")
    show_user_details.short_description = "Show user details for selected accesses"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('user-access/', user_flipbook_access_view, name='user-flipbook-access'),
        ]
        return custom_urls + urls


admin.site.register(FlipBookAccess, FlipBookAccessAdmin)

@staff_member_required
def user_flipbook_access_view(request):
    users = User.objects.filter(is_staff=False, is_superuser=False)
    flipbooks = FlipBook.objects.all()
    from .models import FlipBookAccess
    user_flipbook_ids = {}
    for user in users:
        user_flipbook_ids[user.id] = set(FlipBookAccess.objects.filter(user=user).values_list('flipbook_id', flat=True))

    if request.method == 'POST':
        for user in users:
            selected = set(map(int, request.POST.getlist(f'flipbooks_{user.id}')))
            current = user_flipbook_ids[user.id]
            # Add new accesses
            for fb_id in selected - current:
                FlipBookAccess.objects.create(user=user, flipbook_id=fb_id)
            # Remove unselected accesses
            for fb_id in current - selected:
                FlipBookAccess.objects.filter(user=user, flipbook_id=fb_id).delete()
        messages.success(request, "FlipBook access updated for all users.")
        return redirect(request.path)

    context = {
        'users': users,
        'flipbooks': flipbooks,
        'user_flipbook_ids': user_flipbook_ids,
    }
    return render(request, 'admin/user_flipbook_access.html', context)

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'mobile_number']
    search_fields = ['user__username', 'mobile_number']

admin.site.register(UserProfile, UserProfileAdmin)
