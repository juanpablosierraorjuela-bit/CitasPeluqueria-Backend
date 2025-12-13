from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Tenant, Professional, Service, Product, Appointment, ExternalPayment
from django.contrib import messages
from django.db.models import Sum
from django.contrib.auth.models import User
from django.contrib.auth import login 

# --- VISTA PORTADA (TU DISEÑO) ---
def public_home(request):
    peluquerias = Tenant.objects.all()
    # Sacamos lista unica de ciudades para el filtro
    ciudades = peluquerias.values_list('ciudad', flat=True).distinct()
    return render(request, 'salon/index.html', {'peluquerias': peluquerias, 'ciudades': ciudades})

# --- VISTA PARA AGENDAR (CUANDO DAS CLIC EN UNA TARJETA) ---
def booking_page(request, slug):
    # Buscamos por subdomain (que es tu slug)
    tenant = get_object_or_404(Tenant, subdomain=slug)
    services = Service.objects.filter(tenant=tenant)
    pros = Professional.objects.filter(tenant=tenant)
    return render(request, 'salon/agendar.html', {'tenant': tenant, 'services': services, 'pros': pros})

# --- VISTA LOGIN PERSONALIZADO ---
def custom_login(request):
    return redirect('login') # Redirige al login estandar de Django

# --- VISTA AGENDA CLIENTE (Placeholder) ---
def client_agenda(request):
    return render(request, 'salon/mi_agenda.html') # Debes crear este html luego

# --- DASHBOARD (PANEL DUEÑO) ---
@login_required
def dashboard(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if not tenant:
        if request.method == 'POST':
            name = request.POST.get('name')
            subdomain = request.POST.get('subdomain')
            try:
                new_tenant = Tenant.objects.create(name=name, subdomain=subdomain)
                new_tenant.users.add(request.user)
                new_tenant.save()
                messages.success(request, f"¡Bienvenido a {name}!")
                return redirect('panel_negocio')
            except:
                messages.error(request, "ID ocupado.")
        return render(request, 'salon/create_tenant.html')

    professionals = Professional.objects.filter(tenant=tenant)
    external_pros = professionals.filter(is_external=True)
    services = Service.objects.filter(tenant=tenant)
    products = Product.objects.filter(tenant=tenant)
    appointments = Appointment.objects.filter(tenant=tenant).order_by('-date')
    total_sales = appointments.filter(status='COMPLETED').aggregate(Sum('service__price'))['service__price__sum'] or 0

    context = {
        'tenant': tenant,
        'professionals': professionals,
        'external_pros': external_pros,
        'services': services,
        'products': products,
        'appointments': appointments,
        'total_sales': total_sales,
        'show_inventory': True,
        'show_settings': True,
    }
    return render(request, 'salon/dashboard.html', context)

# --- OTRAS VISTAS NECESARIAS ---
@login_required
def inventory_list(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    products = Product.objects.filter(tenant=tenant) if tenant else []
    return render(request, 'salon/inventory_list.html', {'products': products})

@login_required
def add_product(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        Product.objects.create(tenant=tenant, name=request.POST.get('name'), price=request.POST.get('price'), stock=request.POST.get('stock'))
        return redirect('panel_negocio')
    return render(request, 'salon/add_product.html')

@login_required
def invite_external(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        pro = Professional.objects.create(tenant=tenant, name=request.POST.get('name'), phone="000", is_external=True, commission_rate=request.POST.get('commission'))
        domain = request.build_absolute_uri('/')[:-1]
        link = f"{domain}/register-external/{pro.invite_token}/"
        messages.success(request, f"Link: {link}")
        return redirect('panel_negocio')
    return redirect('panel_negocio')

def register_external_view(request, token):
    pro = get_object_or_404(Professional, invite_token=token)
    if request.method == 'POST':
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        pro.phone = phone
        pro.payment_info = request.POST.get('payment_info')
        pro.telegram_chat_id = request.POST.get('telegram')
        if not User.objects.filter(username=phone).exists():
            user = User.objects.create_user(username=phone, password=password)
            pro.user = user
        pro.save()
        messages.success(request, "Registro Exitoso")
        return redirect('login')
    return render(request, 'salon/register_external.html', {'pro': pro})

@login_required
def pay_external(request, pro_id):
    pro = get_object_or_404(Professional, id=pro_id)
    if request.method == 'POST':
        amount = float(request.POST.get('amount'))
        ExternalPayment.objects.create(professional=pro, amount=amount)
        pro.balance_due = float(pro.balance_due) - amount
        pro.save()
    return redirect('panel_negocio')

@login_required
def settings_view(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        tenant.nequi_number = request.POST.get('nequi')
        tenant.bold_api_key = request.POST.get('bold')
        tenant.save()
    return render(request, 'salon/settings.html', {'tenant': tenant})


# --- VISTA LANDING PAGE (VENTAS) ---
def landing_saas_view(request):
    # Si el usuario ya está logueado y tiene negocio, mejor lo mandamos al dashboard directo
    if request.user.is_authenticated and request.user.tenants.exists():
        return redirect('panel_negocio')
    return render(request, 'salon/landing_saas.html')
