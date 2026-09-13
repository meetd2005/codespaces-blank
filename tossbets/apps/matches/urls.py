from django.urls import path
from . import views

app_name = "matches"

urlpatterns = [
    path("", views.lobby, name="lobby"),
    path("<int:pk>/", views.match_detail, name="detail"),
    path("<int:pk>/bet/", views.place_bet, name="place_bet"),
    path("my-bets/", views.my_bets, name="my_bets"),
]
