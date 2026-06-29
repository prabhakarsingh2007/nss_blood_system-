from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("eligibility/", views.eligibility_checker, name="eligibility_checker"),
]

