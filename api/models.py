

from django.db import models
from django.contrib.auth.models import User


class Group(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

class Member(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)

class Expense(models.Model):
    group = models.ForeignKey(
        Group,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_by = models.ForeignKey(User, on_delete=models.CASCADE)
    split_between = models.ManyToManyField(Member, related_name='shared_expenses')
    created_at = models.DateTimeField(auto_now_add=True)

class ExpenseSplitBetween(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE)
    owe_id = models.ForeignKey(User, on_delete=models.CASCADE)
    amount_owed = models.PositiveIntegerField(default=0)

class Friend(models.Model):
    user1 = models.ForeignKey(User, related_name='friendships_initiated', on_delete=models.CASCADE)
    user2 = models.ForeignKey(User, related_name='friendships_received', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user1', 'user2')

    def __str__(self):
        return f"{self.user1.username} is friends with {self.user2.username}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    username = models.CharField(max_length=255)
    email = models.CharField(max_length=255)


class Request(models.Model):
    from_user = models.ForeignKey(User, related_name='sent_requests', on_delete=models.CASCADE)
    to_user = models.ForeignKey(User, related_name='received_requests', on_delete=models.CASCADE)
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.from_user.username} ➝ {self.to_user.username} [{self.status}]"


class Settlement(models.Model):

    from_user = models.ForeignKey(User, related_name="settlements_made", on_delete=models.CASCADE)
    to_user = models.ForeignKey(User, related_name="settlements_received", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    remark = models.TextField(blank=True, null=True)
    settled_at = models.DateTimeField(auto_now_add=True)
    group = models.ForeignKey(
        Group,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )


    def __str__(self):
        return f"{self.from_user} paid {self.to_user} ₹{self.amount}"

