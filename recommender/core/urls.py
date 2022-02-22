from django.urls import path
from .views import current_user, UserList, change_password

urlpatterns = [
    path('change-password/', change_password),
    path('current_user/', current_user),
    path('users/', UserList.as_view())
]