from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Account, Expense, ExpenseCategory, Transaction, Transfer


@admin.register(Account)
class AccountAdmin(SimpleHistoryAdmin):
    list_display = ("name", "kind", "account_number", "show_on_documents", "is_active")


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")


@admin.register(Expense)
class ExpenseAdmin(SimpleHistoryAdmin):
    list_display = ("date", "description", "category", "amount", "account", "project", "status")
    list_filter = ("status", "category", "account")
    search_fields = ("description", "payee", "reference")
    readonly_fields = ("amount", "account", "status")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("date", "account", "direction", "kind", "amount", "description", "is_void")
    list_filter = ("account", "direction", "kind", "is_void")
    search_fields = ("description", "reference")

    # Transactions are written by services only.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ("date", "from_account", "to_account", "amount", "fee", "status")
