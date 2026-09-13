from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    # Deposit
    path("deposit/", views.deposit_request, name="deposit_request"),
    path("deposit/<int:pk>/pay/", views.deposit_pay, name="deposit_pay"),
    path("deposit/<int:pk>/qr.png", views.deposit_qr_image, name="deposit_qr"),
    path("deposits/", views.deposit_list, name="deposit_list"),
    # Withdrawal
    path("withdraw/", views.withdrawal_request, name="withdrawal_request"),
    path("withdrawals/", views.withdrawal_list, name="withdrawal_list"),
    # Transactions
    path("transactions/", views.transaction_history, name="transactions"),
]
