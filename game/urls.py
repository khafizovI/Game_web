from django.urls import path
from . import views

app_name = 'game'

urlpatterns = [
    path('host/<int:quiz_id>/', views.host_game, name='host'),
    path('join/', views.join_game, name='join'),
    path('lobby/<str:game_code>/', views.lobby, name='lobby'),
    path('lobby-state/<str:game_code>/', views.lobby_state, name='lobby_state'),
    path('status/<str:game_code>/', views.game_status, name='status'),
    path('play/<str:game_code>/', views.play_game, name='play'),
    path('results/<str:game_code>/', views.game_results, name='results'),
]
