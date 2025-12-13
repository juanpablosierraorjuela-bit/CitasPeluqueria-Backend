from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('settings/', views.settings_view, name='settings'),
    path('inventory/', views.inventory_list, name='inventory'),
    path('inventory/add/', views.add_product, name='add_product'),
    path('invite-pro/', views.invite_external, name='invite_external'),
    path('register-external/<uuid:token>/', views.register_external_view, name='register_external'),
    path('pay-pro/<int:pro_id>/', views.pay_external, name='pay_external'),
]
