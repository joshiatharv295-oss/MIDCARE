from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('services/', views.services, name='services'),
    path('doctors/', views.doctor_list, name='doctor_list'),
    path('doctors/add/', login_required(views.add_doctor), name='add_doctor'),
    path('api/doctors/', views.api_doctors, name='api_doctors'),
    path('api/medicines/', views.medicines_list, name='medicines_list'),
    path('api/appointments/', views.create_appointment, name='create_appointment'),
    path('api/my-appointments/', views.my_appointments, name='my_appointments'),
    path('api/orders/', views.place_order, name='place_order'),
    path('api/my-orders/', views.my_orders, name='my_orders'),
    path('api/csrf/', views.csrf_token, name='csrf_token'),
    path('api/me/', views.current_user, name='current_user'),
    path('api/signup/', views.api_signup, name='api_signup'),
    path('api/login/', views.api_login, name='api_login'),
    path('api/logout/', views.api_logout, name='api_logout'),
    path('api/send-otp', views.send_otp, name='send_otp'),
    path('api/verify-otp', views.verify_otp, name='verify_otp'),
    path('api/test/', views.test_chat, name='test_chat'),
    path('api/chatbot/', views.chatbot, name='chatbot'),
    path('appointments/pending/', views.pending_appointments, name='pending_appointments'),
    path('api/pending-appointments/', views.api_pending_appointments, name='api_pending_appointments'),
    path('appointments/doctor/', views.doctor_pending_appointments, name='doctor_pending_appointments'),
    path('api/doctor-appointments/', views.api_doctor_pending_appointments, name='api_doctor_appointments'),
    path('appointments/admin-all/', views.admin_all_appointments, name='admin_all_appointments'),
    path('api/admin-appointments/', views.api_admin_all_appointments, name='api_admin_appointments'),
]
