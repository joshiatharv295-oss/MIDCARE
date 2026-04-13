from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
import json
import random
import logging
import os
from django.views.decorators.http import require_http_methods
from .models import SignupOTP, Doctor, Medicine, Appointment
from .forms import DoctorForm
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


def home(request):
    return render(request, 'base.html')


def services(request):
    """Render the services page with CSRF protection"""
    return render(request, 'services.html')


@require_http_methods(["GET"])
def csrf_token(request):
    from django.middleware.csrf import get_token

    return JsonResponse({"csrfToken": get_token(request)})


@require_http_methods(["GET"])
def current_user(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": True, "authenticated": False})
    return JsonResponse(
        {
            "ok": True,
            "authenticated": True,
            "user": {
                "id": request.user.id,
                "username": request.user.get_username(),
                "email": getattr(request.user, "email", ""),
                "first_name": getattr(request.user, "first_name", ""),
                "last_name": getattr(request.user, "last_name", ""),
            },
        }
    )


@require_http_methods(["POST"])
def api_signup(request):
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        payload = {}
    if not payload:
        payload = request.POST

    first_name = (payload.get("first_name") or "").strip()
    last_name = (payload.get("last_name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    otp_code = (payload.get("otp") or "").strip()

    if not email:
        return JsonResponse({"ok": False, "error": "email is required"}, status=400)
    if not password:
        return JsonResponse({"ok": False, "error": "password is required"}, status=400)
    if not otp_code:
        return JsonResponse({"ok": False, "error": "otp is required"}, status=400)

    otp = SignupOTP.objects.filter(email=email, is_used=False).order_by("-created_at").first()
    if not otp or otp.code != otp_code:
        return JsonResponse({"ok": False, "error": "Invalid or expired OTP"}, status=400)

    User = get_user_model()
    if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
        return JsonResponse({"ok": False, "error": "User already exists"}, status=400)

    try:
        user = User.objects.create_user(username=email, email=email, password=password)
        user.first_name = first_name
        user.last_name = last_name
        user.save(update_fields=["first_name", "last_name"])
    except Exception as e:
        return JsonResponse({"ok": False, "error": f"Unable to create account: {str(e)}"}, status=400)

    otp.is_used = True
    otp.save(update_fields=["is_used"])

    auth_login(request, user)
    return JsonResponse({"ok": True})


@require_http_methods(["POST"])
def api_login(request):
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        payload = {}
    if not payload:
        payload = request.POST

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return JsonResponse({"ok": False, "error": "email and password are required"}, status=400)

    user = authenticate(request, username=email, password=password)
    if user is None:
        return JsonResponse({"ok": False, "error": "Invalid credentials"}, status=400)

    auth_login(request, user)
    return JsonResponse({"ok": True})


@require_http_methods(["POST"])
def api_logout(request):
    auth_logout(request)
    return JsonResponse({"ok": True})


def doctor_list(request):
    """View to list all doctors"""
    doctors = Doctor.objects.all()
    print(f"DEBUG: Found {doctors.count()} doctors in the database")
    for doctor in doctors:
        print(f"DEBUG: Doctor - Name: {doctor.name}, Specialty: {doctor.specialty}")
    return render(request, 'doctors/doctor_list.html', {'doctors': doctors})


@require_http_methods(["GET"])
def api_doctors(request):
    doctors = Doctor.objects.all().order_by("id")
    data = []
    for d in doctors:
        data.append(
            {
                "id": d.id,
                "name": d.name,
                "specialty": getattr(d, "specialty", ""),
                "hospital": getattr(d, "hospital", ""),
                "experience": str(getattr(d, "experience_years", "")),
                "rating": str(getattr(d, "rating", "")),
                "availability": getattr(d, "availability", ""),
                "image": getattr(d, "image_url", "") or "",
            }
        )
    return JsonResponse({"ok": True, "doctors": data})


@login_required
@require_http_methods(["POST"])
def place_order(request):
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        payload = {}
    if not payload:
        payload = request.POST

    items = payload.get("items") or []
    address = payload.get("address") or {}
    payment_method = (payload.get("payment") or "").strip()
    coupon = (payload.get("coupon") or "").strip()

    if not isinstance(items, list) or not items:
        return JsonResponse({"ok": False, "error": "items are required"}, status=400)

    required_addr = ["name", "email", "phone", "address1", "city", "state", "pin"]
    missing = [k for k in required_addr if not (address.get(k) or "").strip()]
    if missing:
        return JsonResponse({"ok": False, "error": f"missing address fields: {', '.join(missing)}"}, status=400)

    if payment_method not in {"COD", "UPI", "Card", "NetBanking"}:
        return JsonResponse({"ok": False, "error": "invalid payment method"}, status=400)

    from django.db import transaction
    from decimal import Decimal
    from .models import Address, Order, OrderItem

    with transaction.atomic():
        shipping = Address.objects.create(
            user=request.user,
            address_type="shipping",
            line1=address.get("address1", ""),
            line2=address.get("address2", ""),
            city=address.get("city", ""),
            state=address.get("state", ""),
            postal_code=address.get("pin", ""),
            country=address.get("country", "India"),
        )

        subtotal = Decimal("0")
        order_items_data = []
        for it in items:
            med_id = it.get("medicine_id")
            qty = int(it.get("quantity") or 0)
            if not med_id or qty <= 0:
                return JsonResponse({"ok": False, "error": "invalid item"}, status=400)
            med = get_object_or_404(Medicine, pk=med_id)
            unit_price = med.price
            line_total = unit_price * qty
            subtotal += line_total
            order_items_data.append((med, qty, unit_price))

        discount = Decimal("0")
        if coupon.upper() == "SAVE10":
            discount = (subtotal * Decimal("0.10")).quantize(Decimal("1."))

        total = subtotal - discount
        if total < 0:
            total = Decimal("0")

        order = Order.objects.create(
            user=request.user,
            total_amount=total,
            status="pending",
            payment_status="pending",
            shipping_address=shipping,
            billing_address=shipping,
        )

        for med, qty, unit_price in order_items_data:
            OrderItem.objects.create(
                order=order,
                medicine=med,
                quantity=qty,
                unit_price=unit_price,
            )

    return JsonResponse(
        {
            "ok": True,
            "order": {
                "id": order.id,
                "subtotal": str(subtotal),
                "discount": str(discount),
                "total": str(total),
                "payment": payment_method,
            },
        },
        status=201,
    )


@login_required
@require_http_methods(["GET"])
def my_orders(request):
    from .models import Order

    orders = (
        Order.objects.filter(user=request.user)
        .select_related("shipping_address")
        .prefetch_related("items__medicine")
        .order_by("-created_at")
    )

    data = []
    for o in orders:
        addr = getattr(o, "shipping_address", None)
        
        # Get order items
        order_items = []
        for item in o.items.all():
            order_items.append({
                "medicine_name": item.medicine.name,
                "medicine_manufacturer": item.medicine.manufacturer or "",
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
                "total_price": str(item.unit_price * item.quantity)
            })
        
        data.append(
            {
                "id": o.id,
                "status": o.status,
                "payment_status": o.payment_status,
                "total_amount": str(o.total_amount),
                "created_at": o.created_at.isoformat() if getattr(o, "created_at", None) else "",
                "updated_at": o.updated_at.isoformat() if getattr(o, "updated_at", None) else "",
                "delivery_time_estimate": getattr(o, "delivery_time_estimate", ""),
                "delivery_notes": getattr(o, "delivery_notes", ""),
                "items": order_items,
                "shipping_address": {
                    "line1": getattr(addr, "line1", "") if addr else "",
                    "line2": getattr(addr, "line2", "") if addr else "",
                    "city": getattr(addr, "city", "") if addr else "",
                    "state": getattr(addr, "state", "") if addr else "",
                    "postal_code": getattr(addr, "postal_code", "") if addr else "",
                    "country": getattr(addr, "country", "") if addr else "",
                },
            }
        )

    return JsonResponse({"ok": True, "orders": data})


@require_http_methods(["GET"])
def medicines_list(request):
    """Return all medicines as JSON for the frontend shop."""
    medicines = Medicine.objects.all()
    data = []
    for med in medicines:
        data.append(
            {
                "id": med.id,
                "name": med.name,
                "type": med.type,
                "price": str(med.price),
                "image_url": med.image.url if getattr(med, "image", None) else "",
                "description": med.description,
                "manufacturer": med.manufacturer,
            }
        )
    return JsonResponse(data, safe=False)


@login_required
def add_doctor(request):
    """View to add a new doctor"""
    if request.method == 'POST':
        form = DoctorForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Doctor added successfully!')
            return redirect('doctor_list')
    else:
        form = DoctorForm()
    return render(request, 'doctors/add_doctor.html', {'form': form})


@csrf_exempt
def test_chat(request):
    """Simple test endpoint"""
    print("TEST ENDPOINT HIT!", flush=True)
    return JsonResponse({'status': 'ok', 'message': 'Test endpoint working'})


@csrf_exempt
def send_otp(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST
    email = (data.get('email') or '').strip().lower()
    if not email:
        return JsonResponse({'error': 'Email is required'}, status=400)

    code = f"{random.randint(100000, 999999)}"
    SignupOTP.objects.create(email=email, code=code)

    try:
        send_mail(
            subject='Your MidCare Signup OTP',
            message=f'Your OTP code is: {code}. It will expire shortly.',
            from_email=(getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None) or 'no-reply@example.com'),
            recipient_list=[email],
            fail_silently=False,
        )
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@csrf_exempt
def verify_otp(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST
    email = (data.get('email') or '').strip()
    code = (data.get('code') or '').strip()
    if not email or not code:
        return JsonResponse({'error': 'Email and code are required'}, status=400)

    otp = SignupOTP.objects.filter(email=email, is_used=False).order_by('-created_at').first()
    if not otp or otp.code != code:
        return JsonResponse({'ok': False, 'error': 'Invalid or expired OTP'}, status=400)

    # Mark as used
    otp.is_used = True
    otp.save(update_fields=['is_used'])
    return JsonResponse({'ok': True})


@csrf_exempt
def chatbot(request):
    """Proxy chatbot requests to Gemini API"""
    logger.info(f"[CHATBOT] Received {request.method} request")
    print(f"[CHATBOT] Received {request.method} request", flush=True)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body.decode('utf-8'))
        logger.info(f"[CHATBOT] Parsed data: {data}")
        print(f"[CHATBOT] Parsed data: {data}", flush=True)
    except Exception as e:
        logger.error(f"[CHATBOT] JSON parse error: {e}")
        print(f"[CHATBOT] JSON parse error: {e}", flush=True)
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    user_message = (data.get('message') or '').strip()
    logger.info(f"[CHATBOT] User message: {user_message}")
    print(f"[CHATBOT] User message: {user_message}", flush=True)
    
    if not user_message:
        return JsonResponse({'error': 'Message is required'}, status=400)
    
    # Get Gemini configuration
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    model = getattr(settings, 'GEMINI_MODEL', 'gemini-1.5-flash')
    
    if not api_key:
        # No API key configured, provide helpful fallback
        return JsonResponse({
            'reply': 'Hello! 👋 I\'m here to help with Medicare services. I can assist you with:\n\n🏥 Medical Services:\n• Booking appointments online\n• Information about our departments (General, Pediatrics, Cardiology, Diagnostics)\n\n💊 Pharmacy:\n• Prescription medicines\n• Over-the-counter products\n• Home delivery options\n\n📞 Contact & Hours:\n• Operating hours and contact information\n\n🌐 Website Navigation:\n• How to use our website\n• Finding the information you need\n\nWhat would you like to know about Medicare?'
        })
    
    # Prepare request to Gemini
    import urllib.request
    import urllib.error
    
    # Try v1 API endpoint (more stable for newer models)
    url = f'https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={api_key}'
    
    # Check for common questions and provide direct answers
    user_lower = user_message.lower()
    
    # Medicine/Pharmacy related queries
    if any(keyword in user_lower for keyword in ['medicine', 'medicines', 'medication', 'drug', 'pharmacy', 'buy', 'purchase', 'order']):
        if any(word in user_lower for word in ['buy', 'purchase', 'order', 'get', 'how to']):
            return JsonResponse({
                'reply': 'To purchase medicines from Medicare Pharmacy:\n\n1. Browse available medicines on our Medicines page\n2. We offer:\n   • Prescription Medications (with valid prescription)\n   • Over-the-Counter (OTC) medicines\n   • Wellness & Health supplements\n\n3. For orders:\n   • Visit us in-person at our pharmacy\n   • Call us for medicine availability\n   • Upload prescription through Contact page\n\n4. Home delivery available for prescription medicines\n\n⚠️ Important: Prescription medicines require a valid doctor\'s prescription. Please consult with our doctors if you need a prescription!\n\nWould you like to know about specific medicines or book a consultation?'
            })
    
    # Appointment related queries
    if any(keyword in user_lower for keyword in ['appointment', 'book', 'schedule', 'how to book', 'how to appointment']):
        if any(word in user_lower for word in ['how', 'book', 'make', 'schedule', 'create']):
            return JsonResponse({
                'reply': 'To book an appointment with Medicare:\n\n1. Visit our Appointments page\n2. Fill in your details (Name, Email, Phone)\n3. Select your preferred date\n4. Choose a department (General, Pediatrics, or Cardiology)\n5. Pick your preferred time (Morning, Afternoon, or Evening)\n6. Add any notes about your concern\n7. Click Submit\n\nOur team will confirm your appointment via email or phone shortly. You can also call us directly for immediate booking assistance!\n\n💡 Tip: After your consultation, you can get prescriptions filled at our pharmacy!'
            })
    
    # Services/Department queries
    if any(keyword in user_lower for keyword in ['department', 'service', 'specialty', 'specialties', 'what do you offer']):
        return JsonResponse({
            'reply': 'Medicare offers comprehensive healthcare services:\n\n🏥 Medical Departments:\n• General Consultation - Routine checkups and common health issues\n• Pediatrics - Specialized care for children and infants\n• Cardiology - Heart and cardiovascular health\n• Diagnostics - Lab tests and medical imaging\n\n💊 Pharmacy Services:\n• Prescription medications\n• Over-the-counter medicines\n• Health supplements & wellness products\n• Home delivery for prescriptions\n\n📅 You can book appointments online or contact us for medicine orders!'
        })
    
    # Contact queries
    if any(keyword in user_lower for keyword in ['contact', 'phone', 'call', 'reach', 'email', 'address']):
        return JsonResponse({
            'reply': 'You can reach Medicare through:\n\n📧 Contact Form: Visit our Contact page\n📅 Appointments: Book online via Appointments page\n💊 Pharmacy: Visit in-person or call for medicine orders\n🏥 Emergency: Available 24/7\n\nOur team is here to help with:\n• Medical consultations\n• Prescription medicines\n• General health inquiries\n\nHow can I assist you today?'
        })
    
    # Hours/Timing queries
    if any(keyword in user_lower for keyword in ['hours', 'timing', 'time', 'open', 'closed', 'available', 'when']):
        return JsonResponse({
            'reply': 'Medicare Operating Hours:\n\n🏥 Medical Services:\n• Mon-Fri: 8:00 AM - 8:00 PM\n• Sat-Sun: 9:00 AM - 6:00 PM\n• Emergency: 24/7\n\n💊 Pharmacy:\n• Mon-Sat: 8:00 AM - 9:00 PM\n• Sunday: 9:00 AM - 7:00 PM\n\n📅 Online appointment booking available 24/7!\n\nWould you like to book an appointment or know more about our services?'
        })
    
    # Help/What can you do queries
    if any(keyword in user_lower for keyword in ['help', 'what can you', 'what do you', 'who are you', 'hello', 'hi', 'hey']):
        return JsonResponse({
            'reply': 'Hello! 👋 I\'m Medicare Assistant. I can help you with:\n\n📋 Common Questions:\n• How to book appointments\n• Available medical services\n• How to purchase medicines\n• Pharmacy operating hours\n• Contact information\n\n💬 Ask me anything about:\n• Medical consultations\n• Health services\n• Prescription medicines\n• Wellness products\n• General health inquiries\n\nWhat would you like to know today?'
        })
    
    # Emergency queries
    if any(keyword in user_lower for keyword in ['emergency', 'urgent', 'serious', 'critical', '911']):
        return JsonResponse({
            'reply': '🚨 EMERGENCY ASSISTANCE:\n\nIf this is a life-threatening emergency:\n• Call emergency services immediately (911 or your local emergency number)\n• Go to the nearest emergency room\n\nFor urgent but non-life-threatening issues:\n• Medicare Emergency Services: Available 24/7\n• Visit our emergency department\n• Call our emergency hotline\n\nCommon Emergency Signs:\n• Chest pain or pressure\n• Difficulty breathing\n• Severe bleeding\n• Loss of consciousness\n• Severe allergic reactions\n\nDon\'t delay - seek immediate medical attention for emergencies!'
        })
    
    # Price/Cost queries
    if any(keyword in user_lower for keyword in ['price', 'cost', 'fee', 'charge', 'payment', 'insurance']):
        return JsonResponse({
            'reply': '💰 Medicare Pricing & Payment:\n\n🏥 Consultation Fees:\n• General Consultation: Competitive rates\n• Specialist Consultation: Varies by department\n• Follow-up visits: Discounted rates\n\n💊 Medicines:\n• Prescription medicines: As per market rates\n• OTC medicines: Clearly marked prices\n• Generic alternatives available\n\n💳 Payment Options:\n• Cash/Card accepted\n• Insurance claims supported\n• Flexible payment plans available\n\n📞 For specific pricing, please contact us or visit in-person. Would you like to book an appointment?'
        })
    
    # Website/Navigation queries
    if any(keyword in user_lower for keyword in ['website', 'site', 'page', 'navigate', 'navigation', 'how to use', 'browse', 'explore', 'menu', 'home']):
        return JsonResponse({
            'reply': '🌐 Navigating Medicare Website:\n\n📄 Main Pages:\n• Home - Overview of our services\n• Services - Detailed medical departments\n• Appointments - Book online consultations\n• Medicines - Browse pharmacy offerings\n• Contact - Get in touch with us\n\n💡 Quick Tips:\n• Use the navigation menu at the top\n• Chat with me anytime (💬 button)\n• All pages are mobile-friendly\n• Secure online appointment booking\n\n🔍 What are you looking for on our website?'
        })
    
    # System instruction integrated into the user prompt for better compatibility
    instruction = '''You are a helpful medical website assistant for Medicare. 

Context about Medicare:
- Medical Services: General Consultation, Pediatrics, Cardiology, and Diagnostics
- Pharmacy: We offer prescription medicines, OTC drugs, and wellness supplements
- Online appointment booking available through our Appointments page
- Booking process: Name, Email, Phone, Date, Department, Time, and Notes
- Medicine orders: Visit pharmacy, call, or upload prescription via Contact page
- Home delivery available for prescription medicines

Guidelines:
- Respond naturally and helpfully in the user's language
- For medical advice, recommend consulting with a healthcare professional
- For appointments, guide users to our online booking form
- For medicines, explain that prescriptions require valid doctor's prescription
- Be conversational, friendly, and informative
- Keep responses concise but complete

Answer the user's question directly and helpfully.'''
    
    # Combine instruction with user message for compatibility
    combined_message = f"{instruction}\n\nUser question: {user_message}\n\nAssistant:"
    
    payload = {
        'contents': [{'parts': [{'text': combined_message}]}],
        'generationConfig': {'temperature': 0.7, 'maxOutputTokens': 500}
    }
    
    logger.info(f"[CHATBOT] Calling Gemini API with model: {model}")
    print(f"[CHATBOT] Calling Gemini API with model: {model}", flush=True)
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        logger.info(f"[CHATBOT] Sending request to Gemini...")
        print(f"[CHATBOT] Sending request to Gemini...", flush=True)
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            logger.info(f"[CHATBOT] Received response from Gemini")
            print(f"[CHATBOT] Received response from Gemini", flush=True)
            parts = result.get('candidates', [{}])[0].get('content', {}).get('parts', [])
            reply_text = ' '.join(p.get('text', '') for p in parts).strip()
            
            if reply_text:
                logger.info(f"[CHATBOT] Reply: {reply_text[:100]}...")
                print(f"[CHATBOT] Reply: {reply_text[:100]}...", flush=True)
                return JsonResponse({'reply': reply_text})
            else:
                logger.warning(f"[CHATBOT] Empty response from Gemini")
                print(f"[CHATBOT] Empty response from Gemini", flush=True)
                # Provide helpful fallback instead of error
                return JsonResponse({
                    'reply': 'I can help you with:\n\n• Booking appointments - Visit our Appointments page\n• Information about our services (General, Pediatrics, Cardiology, Diagnostics)\n• Contacting our team\n\nWhat would you like to know?'
                })
                
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"[CHATBOT] HTTPError {e.code}: {error_body[:200]}")
        print(f"[CHATBOT] HTTPError {e.code}: {error_body[:200]}", flush=True)
        
        # Provide user-friendly error message instead of raw error
        return JsonResponse({
            'reply': 'I apologize, but I\'m having trouble connecting to my AI service right now. However, I can still help you!\n\nFor appointments: Visit our Appointments page to book online.\nFor services: We offer General Consultation, Pediatrics, Cardiology, and Diagnostics.\nFor contact: Visit our Contact page.\n\nWhat would you like to know more about?'
        })
    except Exception as e:
        import traceback
        logger.error(f"[CHATBOT] Exception: {type(e).__name__}: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"[CHATBOT] Exception: {type(e).__name__}: {str(e)}", flush=True)
        print(traceback.format_exc(), flush=True)
        
        # Provide user-friendly error message
        return JsonResponse({
            'reply': 'I apologize for the technical difficulty. Here\'s what I can help you with:\n\n• Book an appointment on our Appointments page\n• Learn about our services: General, Pediatrics, Cardiology, Diagnostics\n• Contact us through our Contact page\n\nHow can I assist you today?'
        })


@login_required
@require_http_methods(["POST"])
def create_appointment(request):
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        payload = {}

    if not payload:
        payload = request.POST

    doctor_id = payload.get("doctor_id")
    date = payload.get("date")
    time = payload.get("time")
    reason = payload.get("reason", "")

    if not doctor_id:
        return JsonResponse({"ok": False, "error": "doctor_id is required"}, status=400)
    if not date:
        return JsonResponse({"ok": False, "error": "date is required"}, status=400)
    if not time:
        return JsonResponse({"ok": False, "error": "time is required"}, status=400)

    try:
        date = datetime.strptime(str(date), "%Y-%m-%d").date()
    except Exception:
        return JsonResponse({"ok": False, "error": "date must be YYYY-MM-DD"}, status=400)

    try:
        time_str = str(time)
        fmt = "%H:%M:%S" if len(time_str.split(":")) == 3 else "%H:%M"
        time = datetime.strptime(time_str, fmt).time()
    except Exception:
        return JsonResponse({"ok": False, "error": "time must be HH:MM or HH:MM:SS"}, status=400)

    doctor = get_object_or_404(Doctor, pk=doctor_id)

    appt = Appointment.objects.create(
        user=request.user,
        doctor=doctor,
        date=date,
        time=time,
        reason=reason,
        status="Pending",
    )

    return JsonResponse(
        {
            "ok": True,
            "appointment": {
                "id": appt.id,
                "doctor": appt.doctor_id,
                "date": str(appt.date),
                "time": appt.time.isoformat(),
                "reason": appt.reason,
                "status": appt.status,
            },
        },
        status=201,
    )


@login_required
@require_http_methods(["GET"])
def my_appointments(request):
    appts = (
        Appointment.objects.filter(user=request.user)
        .select_related("doctor")
        .order_by("-created_at")
    )
    data = []
    for a in appts:
        data.append(
            {
                "id": a.id,
                "doctor": {
                    "id": a.doctor_id,
                    "name": getattr(a.doctor, "name", ""),
                    "specialty": getattr(a.doctor, "specialty", ""),
                },
                "date": str(a.date),
                "time": a.time.isoformat() if getattr(a, "time", None) else "",
                "reason": a.reason,
                "status": a.status,
                "created_at": a.created_at.isoformat() if getattr(a, "created_at", None) else "",
            }
        )
    return JsonResponse({"ok": True, "appointments": data})


@login_required
def pending_appointments(request):
    """Display pending appointments for admin/staff users"""
    # Check if user is staff or admin
    if not (request.user.is_staff or request.user.is_superuser):
        return render(request, '403.html', status=403)
    
    # Get all pending appointments with related doctor and user info
    pending_appts = (
        Appointment.objects.filter(status="Pending")
        .select_related("doctor", "user")
        .order_by("date", "time")
    )
    
    context = {
        "appointments": pending_appts,
        "total_pending": pending_appts.count(),
    }
    return render(request, 'appointments_pending.html', context)


@require_http_methods(["GET", "POST"])
@csrf_exempt
@login_required
def api_pending_appointments(request):
    """API endpoint for fetching pending appointments"""
    # Check if user is staff or admin
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=403)
    
    if request.method == "GET":
        # Fetch all pending appointments
        pending_appts = (
            Appointment.objects.filter(status="Pending")
            .select_related("doctor", "user")
            .order_by("date", "time")
        )
        
        data = []
        for a in pending_appts:
            phone = ""
            if hasattr(a.user, "userprofile"):
                phone = getattr(a.user.userprofile, "phone", "")
            
            data.append({
                "id": a.id,
                "doctor": {
                    "id": a.doctor_id,
                    "name": getattr(a.doctor, "name", ""),
                    "specialty": getattr(a.doctor, "specialty", ""),
                },
                "patient": {
                    "id": a.user_id,
                    "name": a.user.get_full_name() or a.user.username,
                    "email": a.user.email,
                    "phone": phone,
                },
                "date": str(a.date),
                "time": a.time.isoformat() if getattr(a, "time", None) else "",
                "reason": a.reason,
                "status": a.status,
                "created_at": a.created_at.isoformat() if getattr(a, "created_at", None) else "",
            })
        
        return JsonResponse({"ok": True, "appointments": data})
    
    elif request.method == "POST":
        # Update appointment status
        try:
            data = json.loads(request.body.decode('utf-8'))
            appointment_id = data.get('appointment_id')
            new_status = data.get('status')
            
            if new_status not in ['Pending', 'Confirmed', 'Completed', 'Cancelled']:
                return JsonResponse({"ok": False, "error": "Invalid status"}, status=400)
            
            appointment = Appointment.objects.get(id=appointment_id)
            appointment.status = new_status
            appointment.save()
            
            return JsonResponse({
                "ok": True, 
                "message": f"Appointment status updated to {new_status}",
                "appointment": {
                    "id": appointment.id,
                    "status": appointment.status,
                }
            })
        except Appointment.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Appointment not found"}, status=404)
        except Exception as e:
            logger.error(f"Error updating appointment: {e}")
            return JsonResponse({"ok": False, "error": str(e)}, status=400)


@login_required
def doctor_pending_appointments(request):
    """Display pending appointments for logged-in doctor"""
    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return render(request, '403.html', {'message': 'You are not registered as a doctor'}, status=403)
    
    pending_appts = (
        Appointment.objects.filter(doctor=doctor, status="Pending")
        .select_related("doctor", "user")
        .order_by("date", "time")
    )
    
    context = {
        "appointments": pending_appts,
        "total_pending": pending_appts.count(),
        "doctor_name": doctor.name,
    }
    return render(request, 'doctor_pending_appointments.html', context)


@require_http_methods(["GET", "POST"])
@csrf_exempt
@login_required
def api_doctor_pending_appointments(request):
    """API endpoint for doctor's pending appointments"""
    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Not a registered doctor"}, status=403)
    
    if request.method == "GET":
        pending_appts = (
            Appointment.objects.filter(doctor=doctor, status="Pending")
            .select_related("doctor", "user")
            .order_by("date", "time")
        )
        
        data = []
        for a in pending_appts:
            phone = ""
            if hasattr(a.user, "userprofile"):
                phone = getattr(a.user.userprofile, "phone", "")
            
            data.append({
                "id": a.id,
                "doctor": {
                    "id": a.doctor_id,
                    "name": getattr(a.doctor, "name", ""),
                    "specialty": getattr(a.doctor, "specialty", ""),
                },
                "patient": {
                    "id": a.user_id,
                    "name": a.user.get_full_name() or a.user.username,
                    "email": a.user.email,
                    "phone": phone,
                },
                "date": str(a.date),
                "time": a.time.isoformat() if getattr(a, "time", None) else "",
                "reason": a.reason,
                "status": a.status,
                "created_at": a.created_at.isoformat() if getattr(a, "created_at", None) else "",
            })
        
        return JsonResponse({"ok": True, "appointments": data})
    
    elif request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))
            appointment_id = data.get('appointment_id')
            new_status = data.get('status')
            
            if new_status not in ['Pending', 'Confirmed', 'Completed', 'Cancelled']:
                return JsonResponse({"ok": False, "error": "Invalid status"}, status=400)
            
            appointment = Appointment.objects.get(id=appointment_id, doctor=doctor)
            appointment.status = new_status
            appointment.save()
            
            return JsonResponse({
                "ok": True, 
                "message": f"Appointment status updated to {new_status}",
                "appointment": {
                    "id": appointment.id,
                    "status": appointment.status,
                }
            })
        except Appointment.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Appointment not found or not yours"}, status=404)
        except Exception as e:
            logger.error(f"Error updating appointment: {e}")
            return JsonResponse({"ok": False, "error": str(e)}, status=400)


@login_required
def admin_all_appointments(request):
    """Display all appointments for admin"""
    if not (request.user.is_staff or request.user.is_superuser):
        return render(request, '403.html', {'message': 'Only admins can view all appointments'}, status=403)
    
    all_appts = (
        Appointment.objects.all()
        .select_related("doctor", "user")
        .order_by("date", "time")
    )
    
    context = {
        "appointments": all_appts,
        "total_appointments": all_appts.count(),
        "pending_count": all_appts.filter(status="Pending").count(),
    }
    return render(request, 'admin_all_appointments.html', context)


@require_http_methods(["GET", "POST"])
@csrf_exempt
@login_required
def api_admin_all_appointments(request):
    """API endpoint for admin - all appointments"""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=403)
    
    if request.method == "GET":
        all_appts = (
            Appointment.objects.all()
            .select_related("doctor", "user")
            .order_by("date", "time")
        )
        
        data = []
        for a in all_appts:
            phone = ""
            if hasattr(a.user, "userprofile"):
                phone = getattr(a.user.userprofile, "phone", "")
            
            data.append({
                "id": a.id,
                "doctor": {
                    "id": a.doctor_id,
                    "name": getattr(a.doctor, "name", ""),
                    "specialty": getattr(a.doctor, "specialty", ""),
                },
                "patient": {
                    "id": a.user_id,
                    "name": a.user.get_full_name() or a.user.username,
                    "email": a.user.email,
                    "phone": phone,
                },
                "date": str(a.date),
                "time": a.time.isoformat() if getattr(a, "time", None) else "",
                "reason": a.reason,
                "status": a.status,
                "created_at": a.created_at.isoformat() if getattr(a, "created_at", None) else "",
            })
        
        return JsonResponse({"ok": True, "appointments": data})
    
    elif request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))
            appointment_id = data.get('appointment_id')
            new_status = data.get('status')
            
            if new_status not in ['Pending', 'Confirmed', 'Completed', 'Cancelled']:
                return JsonResponse({"ok": False, "error": "Invalid status"}, status=400)
            
            appointment = Appointment.objects.get(id=appointment_id)
            appointment.status = new_status
            appointment.save()
            
            return JsonResponse({
                "ok": True, 
                "message": f"Appointment status updated to {new_status}",
                "appointment": {
                    "id": appointment.id,
                    "status": appointment.status,
                }
            })
        except Appointment.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Appointment not found"}, status=404)
        except Exception as e:
            logger.error(f"Error updating appointment: {e}")
            return JsonResponse({"ok": False, "error": str(e)}, status=400)
