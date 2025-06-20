from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views import (
    register, login_view, UserSearchView,
    FriendRequestViewSet, FriendListView, AddExpenseView, SettleUpView, get_owed_expenses, AllRelatedExpensesView,
    ExpensesBetweenUsersView, SettlementsBetweenUsersView, GroupCreateWithInvitesView, GroupListView,
    get_group_expenses, get_group_settlements, GroupSettleUpView, group_members,
)

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


router = DefaultRouter()
router.register(r'friend-requests', FriendRequestViewSet, basename='friend-request')

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', login_view),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('search-users/', UserSearchView.as_view(), name='search-users'),
    path('friends/', FriendListView.as_view(), name='friend-list'),
    path('expenses/add/', AddExpenseView.as_view(), name='add-expense'),
    path('settle-up/', SettleUpView.as_view(), name='settle-up'),
    path('owed-expenses/<int:user_id>/', get_owed_expenses),
    path('expenses/all/', AllRelatedExpensesView.as_view(), name='all_related_expenses'),
    path('expenses/with/<int:friend_id>/', ExpensesBetweenUsersView.as_view(), name='expenses-with-friend'),
    path('settlements/', views.get_settlements),
    path('settlements/with/<int:friend_id>/', SettlementsBetweenUsersView.as_view(),name='settlement-with-friend'),
    path('groups/', GroupListView.as_view(), name='group-list'),
    path('groups/create/', GroupCreateWithInvitesView.as_view(), name='group-create'),
    path('', include(router.urls)),
    path('group/<int:group_id>/expenses/', get_group_expenses, name='group-expenses'),
    path('group/<int:group_id>/settlements/', get_group_settlements, name='group-settlements'),
    path('group/<int:group_id>/settleup/', GroupSettleUpView.as_view()),
    path('group/<int:group_id>/members/', group_members, name='group-members'),
    path('balance/', views.get_overall_balance, name='get_overall_balance'),
]
