from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from .forms import UsernameMobileAuthenticationForm
from django.contrib.auth.models import User
from django.contrib import messages
import json
from .models import FlipBook, BookView, Event, FlipBookAccess, UserProfile


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def register_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        mobile_number = request.POST.get('mobile_number')
        if form.is_valid():
            user = form.save()
            # Save mobile number
            UserProfile.objects.create(user=user, mobile_number=mobile_number)
            messages.success(request, "Account created successfully! Please log in.")
            return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserCreationForm()
    
    return render(request, 'books/register.html', {'form': form})


def login_view(request):
    """User login view (username, mobile, and password required)"""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = UsernameMobileAuthenticationForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('home')
        else:
            messages.error(request, "Invalid login details.")
    else:
        form = UsernameMobileAuthenticationForm()

    return render(request, 'books/login.html', {'form': form})


def logout_view(request):
    """User logout view"""
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('login')


@login_required
def home_view(request):
    """Home page - list only flipbooks user can access, with event filtering"""
    accessible_ids = FlipBookAccess.objects.filter(user=request.user).values_list('flipbook_id', flat=True)
    books = FlipBook.objects.filter(is_published=True, id__in=accessible_ids)
    events = Event.objects.filter(is_active=True)
    
    # Get selected event from query parameter
    selected_event = request.GET.get('event', None)
    if selected_event:
        try:
            selected_event = int(selected_event)
            books = books.filter(event_id=selected_event)
        except (ValueError, TypeError):
            selected_event = None
    
    # Gender sub-filter
    selected_gender = request.GET.get('gender', None)
    if selected_gender == 'girl':
        books = books.filter(title__icontains='girl')
    elif selected_gender == 'boy':
        books = books.filter(title__icontains='boy')

    context = {
        'books': books,
        'events': events,
        'selected_event': selected_event,
        'selected_gender': selected_gender,
    }
    return render(request, 'books/home.html', context)


@login_required
def flipbook_view(request, book_id):
    """View individual flipbook only if user has access"""
    # Check access
    if not FlipBookAccess.objects.filter(user=request.user, flipbook_id=book_id).exists():
        messages.error(request, "You do not have access to this booklet.")
        return redirect('home')
    
    book = get_object_or_404(FlipBook, id=book_id, is_published=True)
    
    # Track view
    BookView.objects.create(
        book=book,
        user=request.user if request.user.is_authenticated else None,
        ip_address=get_client_ip(request)
    )
    
    # Get all page URLs
    pages = book.get_pages()
    
    context = {
        'book': book,
        'pages': json.dumps(pages),  # Convert to JSON for JavaScript
        'total_pages': book.total_pages,
    }
    
    return render(request, 'books/flipbook.html', context)
