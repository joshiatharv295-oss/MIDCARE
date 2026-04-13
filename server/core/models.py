from django.conf import settings
from django.db import models


class Doctor(models.Model):
    name = models.CharField(max_length=120)
    specialty = models.CharField(max_length=100)
    experience_years = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    availability = models.CharField(max_length=120, blank=True)
    hospital = models.CharField(max_length=150, blank=True)
    image_url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.specialty})"


class Medicine(models.Model):
    TYPE_CHOICES = (
        ("Prescription", "Prescription"),
        ("OTC", "OTC"),
        ("Wellness", "Wellness"),
    )
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="medicines/", blank=True, null=True)
    description = models.TextField(blank=True)
    manufacturer = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20, blank=True)
    blood_group = models.CharField(max_length=5, blank=True)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f"Profile: {self.user.username}"


class Appointment(models.Model):
    STATUS_CHOICES = (
        ("Pending", "Pending"),
        ("Confirmed", "Confirmed"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    date = models.DateField()
    time = models.TimeField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} with {self.doctor} on {self.date} {self.time}"


class SignupOTP(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"OTP for {self.email} ({'used' if self.is_used else 'active'})"


class Address(models.Model):
    """Postal address for shipping/billing."""

    ADDRESS_TYPE_CHOICES = (
        ("shipping", "Shipping"),
        ("billing", "Billing"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(
        max_length=20, choices=ADDRESS_TYPE_CHOICES, default="shipping"
    )
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=120, default="India")
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.address_type} ({self.city})"


class Cart(models.Model):
    """Shopping cart for a user (active or converted to order)."""

    STATUS_CHOICES = (
        ("active", "Active"),
        ("converted", "Converted to order"),
        ("abandoned", "Abandoned"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carts",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart #{self.pk} for {self.user.username} ({self.status})"


class CartItem(models.Model):
    """Individual medicine line item inside a cart."""

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.PROTECT,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per unit at the time of adding to cart.",
    )

    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quantity} × {self.medicine.name} (Cart #{self.cart_id})"


class Order(models.Model):
    """Confirmed order created from a cart."""

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("preparing", "Preparing"),
        ("at_service", "At Service"),
        ("out_for_delivery", "Out for Delivery"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
        ("returned", "Returned"),
    )

    PAYMENT_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    cart = models.OneToOneField(
        Cart,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending"
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    shipping_address = models.ForeignKey(
        Address,
        on_delete=models.PROTECT,
        related_name="shipping_orders",
        null=True,
        blank=True,
    )
    billing_address = models.ForeignKey(
        Address,
        on_delete=models.PROTECT,
        related_name="billing_orders",
        null=True,
        blank=True,
    )
    delivery_time_estimate = models.CharField(
        max_length=100,
        blank=True,
        help_text="Estimated delivery time (e.g., '15 mins to reach', '30-45 mins')"
    )
    delivery_notes = models.TextField(
        blank=True,
        help_text="Additional notes about delivery status or updates"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.pk} for {self.user.username} ({self.status})"


class OrderItem(models.Model):
    """Snapshot of a cart item at the time of order confirmation."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per unit at the time of ordering.",
    )

    def __str__(self):
        return f"{self.quantity} × {self.medicine.name} (Order #{self.order_id})"
