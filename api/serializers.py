
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers

from api.models import Profile, Member, Group, Request, ExpenseSplitBetween, Expense, Settlement

class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].validators = []

    def validate_username(self, value):
        if not all(char.isalnum() or char.isspace() for char in value):
            raise serializers.ValidationError("Username can only contain letters, numbers, and spaces.")
        return value

    def create(self, validated_data):
        email = validated_data['email']
        user = User.objects.create_user(
            username=validated_data['username'],
            email=email,
            password=validated_data['password']
        )
        Profile.objects.create(user=user, username=user.username, email=email)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password")

        user = authenticate(username=user.username, password=password)

        if user is None:
            raise serializers.ValidationError("Invalid email or password")

        data['user'] = user
        return data

class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['name']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class RequestSerializer(serializers.ModelSerializer):
    from_user = UserSerializer(read_only=True)
    to_user = UserSerializer(read_only=True)
    group_name = serializers.SerializerMethodField()

    class Meta:
        model = Request
        fields = '__all__'

    def get_group_name(self, obj):
        return obj.group.name if obj.group else None


class GroupSerializer(serializers.ModelSerializer):
    members = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'name', 'created_at', 'members']

    def get_members(self, obj):
        members = Member.objects.filter(group=obj).select_related('user')
        return [
            {
                'id': m.user.id,
                'username': m.user.username
            }
            for m in members if m.user
        ]



class ExpenseSplitBetweenSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseSplitBetween
        fields = ['owe']

class ExpenseSerializer(serializers.ModelSerializer):
    group = serializers.SlugRelatedField(
        slug_field='name',
        queryset=Group.objects.all(),
        required=False,
        allow_null=True
    )

    paid_by = serializers.HiddenField(default=serializers.CurrentUserDefault())

    owe_list = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField()),
        write_only=True
    )

    class Meta:
        model = Expense
        fields = ['id', 'description', 'amount', 'group', 'paid_by', 'owe_list' ]

    def create(self, validated_data):
        owe_list = validated_data.pop('owe_list', [])
        expense = Expense.objects.create(**validated_data)

        for entry in owe_list:
            username = entry.get('username')
            amount_owed = entry.get('amount_owed')

            try:
                user = User.objects.get(username=username)
                ExpenseSplitBetween.objects.create(
                    expense=expense,
                    owe_id=user,
                    amount_owed=int(amount_owed)
                )
            except User.DoesNotExist:
                raise serializers.ValidationError(f"User '{username}' does not exist.")
            except Exception as e:
                raise serializers.ValidationError(f"Error processing '{username}': {str(e)}")

        return expense


class OwedExpenseSerializer(serializers.ModelSerializer):
    description = serializers.CharField(source='expense.description')
    total_amount = serializers.DecimalField(source='expense.amount', max_digits=10, decimal_places=2)
    paid_by = serializers.CharField(source='expense.paid_by.username')
    group = serializers.CharField(source='expense.group.name', allow_null=True)
    amount_owe = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseSplitBetween
        fields = ['id', 'description', 'amount_owe', 'total_amount', 'paid_by', 'group']

    def get_amount_owe(self, obj):
        return obj.amount_owed

class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']

class FilteredSplitSerializer(serializers.ModelSerializer):
    owe_id = UserBasicSerializer()

    class Meta:
        model = ExpenseSplitBetween
        fields = ['owe_id', 'amount_owed']

class DetailedExpenseWithSplitsSerializer(serializers.ModelSerializer):
    paid_by = UserBasicSerializer()
    splits = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%SZ", read_only=True)

    class Meta:
        model = Expense
        fields = ['id', 'description', 'amount', 'paid_by', 'group', 'splits', "created_at"]

    def get_splits(self, expense):
        user = self.context['user']
        friend_id = self.context['friend_id']
        splits = ExpenseSplitBetween.objects.filter(
            expense=expense,
            owe_id__in=[user.id, friend_id]
        ).select_related('owe_id')
        return FilteredSplitSerializer(splits, many=True).data


class SettlementSerializer(serializers.ModelSerializer):
    from_user_username = serializers.CharField(source="from_user.username", read_only=True)
    to_user_username = serializers.CharField(source="to_user.username", read_only=True)

    class Meta:
        model = Settlement
        fields = ['id', 'from_user', 'to_user', 'from_user_username', 'to_user_username', 'amount', 'remark', 'settled_at' , 'group']


class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']

class SplitDetailSerializer(serializers.ModelSerializer):
    owe_id = UserMiniSerializer()

    class Meta:
        model = ExpenseSplitBetween
        fields = ['owe_id', 'amount_owed']

class GroupExpenseSerializer(serializers.ModelSerializer):
    paid_by = UserMiniSerializer()
    splits = serializers.SerializerMethodField()
    group = serializers.CharField(source='group.name')
    created_at = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%SZ", read_only=True)

    class Meta:
        model = Expense
        fields = ['id', 'description', 'amount', 'group', 'paid_by', 'splits', 'created_at']

    def get_splits(self, obj):
        splits = ExpenseSplitBetween.objects.filter(expense=obj)
        return SplitDetailSerializer(splits, many=True).data



class IndividualSettlementSerializer(serializers.Serializer):
    to_user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

class GroupSettleUpSerializer(serializers.Serializer):
    from_user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), required=False, allow_null=True)
    settlements = IndividualSettlementSerializer(many=True)
    remark = serializers.CharField(required=False, allow_blank=True)


    def create(self, validated_data):
        from_user = validated_data['from_user']
        group = validated_data['group']
        settlements_data = validated_data['settlements']


        created = []
        for entry in settlements_data:
            to_user = entry['to_user']
            amount = entry['amount']
            settlement = Settlement.objects.create(
                from_user=from_user,
                to_user=to_user,
                amount=amount,
                group=group,
                remark=entry.get('remark', '')
            )
            created.append(settlement)

        return created
