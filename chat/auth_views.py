"""
Authentication views for the findus application.

This module contains views for user authentication including login, logout, and registration.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.http import HttpRequest, HttpResponse


def login_view(request: HttpRequest) -> HttpResponse:
    """
    Handle user login.

    Args:
        request: The HTTP request object

    Returns:
        Rendered login template or redirect to home page
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {username}!")
                # Redirect to the page user was trying to access, or home
                next_page = request.GET.get('next', 'home')
                return redirect(next_page)
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'chat/login.html', {'form': form})


def logout_view(request: HttpRequest) -> HttpResponse:
    """
    Handle user logout.

    Args:
        request: The HTTP request object

    Returns:
        Redirect to login page
    """
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('login')


def register_view(request: HttpRequest) -> HttpResponse:
    """
    Handle user registration.

    Args:
        request: The HTTP request object

    Returns:
        Rendered registration template or redirect to login page
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(
                request, f"Account created for {username}! You can now log in."
            )
            return redirect('login')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = UserCreationForm()

    return render(request, 'chat/register.html', {'form': form})
