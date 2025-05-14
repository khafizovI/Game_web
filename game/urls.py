from django.urls import path
from . import views

app_name = 'game'

urlpatterns = [
    path('host/<int:quiz_id>/', views.host_game, name='host'),
    path('host/control/<str:game_code>/', views.host_control, name='host_control'),
    path('join/', views.join_game, name='join'),
    path('play/<str:game_code>/', views.play_game, name='play'),
    path('results/<str:game_code>/', views.game_results, name='results'),
]
