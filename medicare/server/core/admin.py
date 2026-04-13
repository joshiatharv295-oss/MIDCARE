from django.contrib import admin
from django.utils.html import format_html
from urllib.parse import quote
from .models import (
    Doctor,
    Medicine,
    Appointment,
    UserProfile,
    SignupOTP,
    Address,
    Cart,
    CartItem,
    Order,
    OrderItem,
)


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("name", "specialty", "hospital", "rating")
    search_fields = ("name", "specialty", "hospital")


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "price", "manufacturer")
    search_fields = ("name", "manufacturer")
    list_filter = ("type",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("user", "doctor", "date", "time", "status")
    list_filter = ("status", "date")
    search_fields = ("user__username", "doctor__name")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "blood_group")
    search_fields = ("user__username", "phone")


@admin.register(SignupOTP)
class SignupOTPAdmin(admin.ModelAdmin):
    list_display = ("email", "code", "is_used", "created_at")
    list_filter = ("is_used", "created_at")
    search_fields = ("email",)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("user", "address_type", "city", "state", "country", "is_default")
    list_filter = ("address_type", "country", "is_default")
    search_fields = ("user__username", "city", "state", "postal_code")


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__username",)
    inlines = [CartItemInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    actions = ['mark_as_confirmed', 'mark_as_preparing', 'mark_as_out_for_delivery', 'mark_as_delivered', 'mark_as_cancelled']
    
    def shipping_city(self, obj):
        addr = getattr(obj, "shipping_address", None)
        return getattr(addr, "city", "") if addr else ""
    
    def mark_as_confirmed(self, request, queryset):
        queryset.update(status='confirmed')
        self.message_user(request, f"{queryset.count()} orders marked as confirmed.")
    mark_as_confirmed.short_description = "Mark selected orders as confirmed"
    
    def mark_as_preparing(self, request, queryset):
        queryset.update(status='preparing')
        self.message_user(request, f"{queryset.count()} orders marked as preparing.")
    mark_as_preparing.short_description = "Mark selected orders as preparing"
    
    def mark_as_out_for_delivery(self, request, queryset):
        queryset.update(status='out_for_delivery')
        self.message_user(request, f"{queryset.count()} orders marked as out for delivery.")
    mark_as_out_for_delivery.short_description = "Mark selected orders as out for delivery"
    
    def mark_as_delivered(self, request, queryset):
        queryset.update(status='delivered')
        self.message_user(request, f"{queryset.count()} orders marked as delivered.")
    mark_as_delivered.short_description = "Mark selected orders as delivered"
    
    def mark_as_cancelled(self, request, queryset):
        queryset.update(status='cancelled')
        self.message_user(request, f"{queryset.count()} orders marked as cancelled.")
    mark_as_cancelled.short_description = "Mark selected orders as cancelled"

    def shipping_address_text(self, obj):
        addr = getattr(obj, "shipping_address", None)
        if not addr:
            return ""
        parts = [addr.line1, addr.line2, addr.city, addr.state, addr.postal_code, addr.country]
        return ", ".join([p for p in parts if p])

    def shipping_map(self, obj):
        text = self.shipping_address_text(obj)
        if not text:
            return ""
        q = quote(text)
        url = f"https://www.google.com/maps?q={q}"
        return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">View Map</a>', url)

    def colored_status(self, obj):
        colors = {
            "pending": "#FFA500",      # Orange
            "confirmed": "#007BFF",    # Blue
            "preparing": "#17A2B8",    # Cyan
            "at_service": "#6F42C1",   # Purple
            "out_for_delivery": "#28A745", # Green
            "delivered": "#20C997",     # Teal
            "cancelled": "#DC3545",      # Red
            "returned": "#6C757D",       # Gray
        }
        color = colors.get(obj.status, "#6C757D")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )

    def order_items_count(self, obj):
        return obj.items.count()

    list_display = (
        "id",
        "user",
        "status",
        "colored_status",
        "payment_status",
        "total_amount",
        "order_items_count",
        "shipping_city",
        "delivery_time_estimate",
        "shipping_map",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "status", 
        "payment_status", 
        "created_at", 
        "updated_at"
    )
    search_fields = (
        "user__username", 
        "user__email", 
        "id",
        "shipping_address__city",
        "shipping_address__postal_code"
    )
    
    # Make fields editable directly in list view
    list_editable = ("status", "payment_status", "delivery_time_estimate")
    
    # Field ordering and grouping
    fieldsets = (
        ("Order Information", {
            "fields": ("user", "status", "payment_status", "total_amount")
        }),
        ("Delivery Information", {
            "fields": (
                "shipping_address", 
                "billing_address", 
                "delivery_time_estimate",
                "delivery_notes"
            )
        }),
        ("System Information", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    # Show all fields
    readonly_fields = ("created_at", "updated_at")
    
    # Add inline order items
    inlines = [OrderItemInline]
    
    # Pagination
    list_per_page = 25
    
    # Ordering
    ordering = ("-created_at",)
