from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('login/', views.login_view, name='login'),  
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.profile, name='dashboard'),
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('history/', views.hosted_history, name='hosted_history'),
    path('shop/', views.shop, name='shop'),
    path('shop/purchase/<int:item_id>/', views.purchase_item, name='purchase_item'),
    path('shop/equip-frame/<int:item_id>/', views.equip_frame, name='equip_frame'),
    path('shop/equip-theme/<int:item_id>/', views.equip_theme, name='equip_theme'),
    path('submit-rating/', views.submit_rating, name='submit_rating'),
    path('complete-task/<int:task_id>/', views.complete_daily_task, name='complete_daily_task'),
]
