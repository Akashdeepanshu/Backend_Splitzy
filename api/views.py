from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.db.models import Q

from .models import Member, Request, Friend, Settlement, ExpenseSplitBetween, Expense, Group
from .serializers import (
    RegisterSerializer, LoginSerializer, MemberSerializer,
    RequestSerializer, UserSerializer, ExpenseSerializer, OwedExpenseSerializer, DetailedExpenseWithSplitsSerializer,
    SettlementSerializer, GroupSerializer, GroupSettleUpSerializer, GroupExpenseSerializer
)

@api_view(['POST'])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "User registered successfully!"}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def login_view(request):
    print("Request Data:", request.data)  # Debug
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return Response({
            "message": "Login successful",
            "username": user.username,
            "email": user.email,
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "Id": user.id
        }, status=200)
    else:
        print("Login errors:", serializer.errors)
    return Response(serializer.errors, status=400)


class UserSearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('email', '')
        if query:
            users = User.objects.filter(
                Q(username__icontains=query) | Q(email__icontains=query)
            ).exclude(id=request.user.id)
        else:
            users = User.objects.none()
        return Response(UserSerializer(users, many=True).data)


class FriendRequestViewSet(viewsets.ModelViewSet):
    queryset = Request.objects.all()
    serializer_class = RequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request):
        to_user_id = request.data.get('to_user_id')
        group_id = request.data.get('group_id')  # optional

        if int(to_user_id) == request.user.id:
            return Response({'error': 'Cannot send request to yourself'}, status=400)

        to_user = User.objects.filter(id=to_user_id).first()
        if not to_user:
            return Response({'error': 'User not found'}, status=404)


        if group_id:
            group = Group.objects.filter(id=group_id).first()
            if not group:
                return Response({'error': 'Group not found'}, status=404)

            existing_request = Request.objects.filter(
                from_user=request.user,
                to_user=to_user,
                group=group,
                status='pending'
            ).first()
            if existing_request:
                return Response({'message': 'Group invite already sent'}, status=400)

            group_request = Request.objects.create(
                from_user=request.user,
                to_user=to_user,
                group=group
            )
            return Response(RequestSerializer(group_request).data, status=201)


        if Friend.objects.filter(
                Q(user1=request.user, user2=to_user) | Q(user1=to_user, user2=request.user)
        ).exists():
            return Response({'error': 'You are already friends with this user'}, status=400)

        existing_friend_request = Request.objects.filter(
            from_user=request.user,
            to_user=to_user,
            group__isnull=True,
            status='pending'
        ).first()
        if existing_friend_request:
            return Response({'message': 'Friend request already sent'}, status=400)

        friend_request = Request.objects.create(
            from_user=request.user,
            to_user=to_user
        )
        return Response(RequestSerializer(friend_request).data, status=201)

    def list(self, request, *args, **kwargs):
        queryset = Request.objects.filter(to_user=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='friends')
    def my_friends(self, request):
        accepted = Request.objects.filter(
            (Q(from_user=request.user) | Q(to_user=request.user)),
            status='accepted'
        )
        friends = []
        for fr in accepted:
            friend = fr.to_user if fr.from_user == request.user else fr.from_user
            friends.append(friend)
        return Response(UserSerializer(friends, many=True).data)

    @action(detail=True, methods=['post'], url_path='accept')
    def accept(self, request, pk=None):
        try:
            friend_request = self.get_object()

            if friend_request.to_user != request.user:
                return Response({'error': 'Not authorized to accept this request'}, status=403)


            if friend_request.group:
                Member.objects.create(
                    group=friend_request.group,
                    name=request.user.username ,
                    user=request.user
                )
                message = 'Group invite accepted and added to group.'
            else:

                user1, user2 = sorted([request.user, friend_request.from_user], key=lambda u: u.id)

                if Friend.objects.filter(user1=user1, user2=user2).exists():
                    friend_request.delete()
                    return Response({'message': 'Already friends. Request deleted.'}, status=200)

                Friend.objects.create(user1=user1, user2=user2)
                message = 'Friend request accepted and friendship created.'

            friend_request.status = 'accepted'
            friend_request.delete()

            return Response({'message': message}, status=200)

        except Request.DoesNotExist:
            return Response({'error': 'Request not found'}, status=404)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        friend_request = self.get_object()
        if friend_request.to_user != request.user:
            return Response({'error': 'Not authorized'}, status=403)
        friend_request.status = 'rejected'
        friend_request.save()

        friend_request.delete()

        return Response({'message': 'Friend request rejected'})


class FriendListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        friend_entries = Friend.objects.filter(Q(user1=user) | Q(user2=user))

        friends = []
        for f in friend_entries:
            friend = f.user2 if f.user1 == user else f.user1
            friends.append(friend)

        return Response(UserSerializer(friends, many=True).data)


class GroupListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user


        member_entries = Member.objects.filter(user=user).select_related('group')


        groups = [member.group for member in member_entries]


        serializer = GroupSerializer(groups, many=True)
        return Response(serializer.data, status=200)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def group_members(request, group_id):
    try:
        group = Group.objects.get(pk=group_id)
        members = Member.objects.filter(group=group).select_related('user')
        data = [
            {"id": m.user.id, "username": m.user.username}
            for m in members
        ]
        return Response(data)
    except Group.DoesNotExist:
        return Response({"error": "Group not found"}, status=404)



class AddExpenseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ExpenseSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(paid_by=request.user)
            return Response({"message": "Expense added successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SettleUpView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from_user = request.user
        to_user_id = request.data.get("to_user_id")
        amount = float(request.data.get("amount"))
        remark = request.data.get("remark")

        if not to_user_id or not amount:
            return Response({"error": "Missing fields"}, status=400)

        to_user = User.objects.get(id=to_user_id)

        with transaction.atomic():

            settlement = Settlement.objects.create(
                from_user=from_user,
                to_user=to_user,
                amount=amount,
                remark=remark,

            )

            remaining_amount = amount

            splits = ExpenseSplitBetween.objects.filter(
                owe_id=from_user,
                expense__paid_by=to_user
            ).order_by('id')

            for split in splits:
                if remaining_amount <= 0:
                    break

                if split.amount_owed <= remaining_amount:
                    remaining_amount -= float(split.amount_owed)
                    split.amount_owed = 0
                else:
                    split.amount_owed -= remaining_amount
                    remaining_amount = 0

                split.save()

        return Response({"message": "Settlement successful"}, status=200)

@api_view(['GET'])
def get_owed_expenses(request, user_id):
    expenses = ExpenseSplitBetween.objects.filter(owe_id=user_id).select_related('expense', 'expense__paid_by', 'expense__group')
    serializer = OwedExpenseSerializer(expenses, many=True)
    return Response(serializer.data)


class AllRelatedExpensesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user


        paid_expenses = Expense.objects.filter(paid_by=user).select_related('group')


        owed_expenses = ExpenseSplitBetween.objects.filter(
            owe_id=user
        ).select_related('expense', 'expense__paid_by', 'expense__group')

        paid_serializer = ExpenseSerializer(paid_expenses, many=True)
        owed_serializer = OwedExpenseSerializer(owed_expenses, many=True)

        return Response({
            "paid": paid_serializer.data,
            "owed": owed_serializer.data
        })

class ExpensesBetweenUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, friend_id):
        user = request.user

        expenses = Expense.objects.filter(
            Q(paid_by=user, expensesplitbetween__owe_id=friend_id) |
            Q(paid_by_id=friend_id, expensesplitbetween__owe_id=user.id)
        ).select_related('paid_by', 'group').prefetch_related('expensesplitbetween_set').distinct()

        serializer = DetailedExpenseWithSplitsSerializer(expenses, many=True, context={'user': user, 'friend_id': friend_id})
        return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_settlements(request):
    settlements = Settlement.objects.filter(from_user=request.user) | Settlement.objects.filter(to_user=request.user)
    serializer = SettlementSerializer(settlements.order_by('-settled_at'), many=True)
    return Response(serializer.data)

class SettlementsBetweenUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, friend_id):
        user = request.user

        settlements = Settlement.objects.filter(
            Q(from_user=user, to_user_id=friend_id) |
            Q(from_user_id=friend_id, to_user=user)
        ).order_by('-settled_at')

        serializer = SettlementSerializer(settlements, many=True)
        return Response(serializer.data)


class GroupCreateWithInvitesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        group_name = request.data.get('name')
        member_ids = request.data.get('member_ids', [])

        if not group_name:
            return Response({"error": "Group name is required"}, status=400)

        group = Group.objects.create(name=group_name)

        for uid in member_ids:
            user = User.objects.filter(id=uid).first()
            if user and user != request.user:
                Request.objects.create(
                    from_user=request.user,
                    to_user=user,
                    group=group,
                    status='pending'
                )


        Member.objects.create(group=group, user=request.user, name=request.user.username)

        return Response(GroupSerializer(group).data, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_group_expenses(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    expenses = Expense.objects.filter(group=group).order_by('-created_at')
    serializer = GroupExpenseSerializer(expenses, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_group_settlements(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    settlements = Settlement.objects.filter(group=group).order_by('-settled_at')
    serializer = SettlementSerializer(settlements, many=True)
    return Response(serializer.data)


class GroupSettleUpView(APIView):
    def post(self, request, group_id):
        data = request.data.copy()
        data['group'] = group_id

        serializer = GroupSettleUpSerializer(data=data)
        if serializer.is_valid():
            settlements = serializer.save()
            return Response({
                "message": "Settlements created",
                "settlements": [s.id for s in settlements]
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_overall_balance(request):
    user = request.user

    you_are_owed = Decimal('0.00')
    you_owe = Decimal('0.00')


    expenses_paid_by_user = Expense.objects.filter(paid_by=user)
    for expense in expenses_paid_by_user:
        splits = ExpenseSplitBetween.objects.filter(expense=expense)
        for split in splits:
            if split.owe_id != user:
                you_are_owed += Decimal(split.amount_owed)


    expenses_owed_by_user = ExpenseSplitBetween.objects.filter(owe_id=user)
    for split in expenses_owed_by_user:
        if split.expense.paid_by != user:
            you_owe += Decimal(split.amount_owed)


    settlements_paid_by_user = Settlement.objects.filter(from_user=user)
    for s in settlements_paid_by_user:
        you_owe -= s.amount

    settlements_received_by_user = Settlement.objects.filter(to_user=user)
    for s in settlements_received_by_user:
        you_are_owed -= s.amount


    final_you_are_owed = abs(you_are_owed)  # always positive
    final_you_owe = -abs(you_owe)           # always negative
    total = final_you_are_owed + final_you_owe

    return Response({
        "you_are_owed": float(round(final_you_are_owed, 2)),
        "you_owe": float(round(final_you_owe, 2)),
        "total": float(round(total, 2))
    })
