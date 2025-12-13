from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Tenant, Professional, Service, Product, Appointment, ExternalPayment
from django.contrib import messages
from django.db.models import Sum
from django.contrib.auth.models import User

@login_required
def dashboard(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    # Si no hay tenant, renderizar error o crear
    if not tenant: return render(request, 'salon/create_tenant.html')
    
    professionals = Professional.objects.filter(tenant=tenant)
    external_pros = professionals.filter(is_external=True)
    internal_pros = professionals.filter(is_external=False)
    services = Service.objects.filter(tenant=tenant)
    products = Product.objects.filter(tenant=tenant)
    appointments = Appointment.objects.filter(tenant=tenant).order_by('-date', '-time')
    
    total_sales = appointments.filter(status='COMPLETED').aggregate(Sum('service__price'))['service__price__sum'] or 0

    context = {
        'tenant': tenant,
        'professionals': professionals,
        'internal_pros': internal_pros,
        'external_pros': external_pros,
        'services': services,
        'products': products,
        'appointments': appointments,
        'total_sales': total_sales,
        'show_inventory': True,
        'show_settings': True,
        'show_notifications': True,
        'show_steps': True,
    }
    # Asegúrate que tu template esté en templates/salon/dashboard.html
    return render(request, 'salon/dashboard.html', context)

@login_required
def inventory_list(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    products = Product.objects.filter(tenant=tenant)
    return render(request, 'salon/inventory_list.html', {'products': products})

@login_required
def add_product(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        name = request.POST.get('name')
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        Product.objects.create(tenant=tenant, name=name, price=price, stock=stock)
        messages.success(request, 'Producto añadido')
        return redirect('dashboard')
    return render(request, 'salon/add_product.html')

@login_required
def invite_external(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        name = request.POST.get('name')
        commission = request.POST.get('commission')
        pro = Professional.objects.create(tenant=tenant, name=name, phone="000", is_external=True, commission_rate=commission)
        domain = request.build_absolute_uri('/')[:-1] 
        link = f"{domain}/register-external/{pro.invite_token}/"
        messages.success(request, f"Link creado: {link}")
        return redirect('dashboard')
    return redirect('dashboard')

def register_external_view(request, token):
    pro = get_object_or_404(Professional, invite_token=token)
    if request.method == 'POST':
        phone = request.POST.get('phone')
        payment_info = request.POST.get('payment_info')
        telegram = request.POST.get('telegram')
        password = request.POST.get('password')
        pro.phone = phone
        pro.payment_info = payment_info
        pro.telegram_chat_id = telegram
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
        messages.success(request, f"Pago registrado")
    return redirect('dashboard')

@login_required
def settings_view(request):
    tenant = Tenant.objects.filter(users=request.user).first()
    if request.method == 'POST':
        tenant.nequi_number = request.POST.get('nequi')
        tenant.bold_api_key = request.POST.get('bold')
        tenant.save()
        messages.success(request, "Configuración guardada")
    return render(request, 'salon/settings.html', {'tenant': tenant})
