import os

print("--- 🎨 IMPLANTANDO TU DISEÑO Y CONECTANDO RUTAS 🎨 ---")

# 1. PEGAR TU CÓDIGO HTML EXACTO EN LA PORTADA
# (Creamos el archivo index.html con TU código)
os.makedirs('salon/templates/salon', exist_ok=True)

html_code = """
{% load static %}
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>PASO | Tu estilo, tu tiempo</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22 font-weight=%22bold%22 fill=%22black%22>P</text></svg>">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root { --font-main: 'Plus Jakarta Sans', sans-serif; --primary: #0f172a; --secondary: #64748b; --accent: #ec4899; --bg-body: #f8fafc; }
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body { font-family: var(--font-main); background-color: var(--bg-body); color: var(--primary); min-height: 100vh; margin: 0; padding: 0; overflow-x: hidden; }
        .ambient-bg { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: -2; background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); overflow: hidden; }
        .blob { position: absolute; filter: blur(80px); opacity: 0.6; animation: float 10s infinite alternate ease-in-out; }
        .blob-1 { top: -10%; left: -10%; width: 500px; height: 500px; background: #fce7f3; }
        .blob-2 { bottom: -10%; right: -10%; width: 600px; height: 600px; background: #e0e7ff; animation-delay: -5s; }
        .blob-3 { top: 40%; left: 40%; width: 300px; height: 300px; background: #fae8ff; animation-delay: -2s; }
        @keyframes float { 0% { transform: translate(0, 0) scale(1); } 100% { transform: translate(30px, 50px) scale(1.1); } }
        .navbar { padding: 20px 40px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border-bottom: 1px solid rgba(255,255,255,0.2); transition: all 0.3s; }
        .navbar.scrolled { background: rgba(255,255,255,0.9); box-shadow: 0 4px 20px rgba(0,0,0,0.03); }
        .brand-pill { text-decoration: none; font-weight: 800; color: var(--primary); font-size: 1.2rem; display: flex; align-items: center; gap: 8px; }
        .dot { width: 8px; height: 8px; background: var(--primary); border-radius: 50%; }
        .btn-access { text-decoration: none; background: var(--primary); color: white; padding: 10px 24px; border-radius: 50px; font-size: 0.9rem; font-weight: 600; transition: transform 0.2s, box-shadow 0.2s; box-shadow: 0 4px 15px rgba(15, 23, 42, 0.2); }
        .btn-access:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(15, 23, 42, 0.3); }
        header { text-align: center; padding: 100px 20px 60px; max-width: 900px; margin: 0 auto; }
        .hero-title { font-size: 4.5rem; font-weight: 800; margin: 0 0 15px; line-height: 1.05; letter-spacing: -2px; background: linear-gradient(180deg, #0f172a 20%, #475569 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; animation: fadeUp 0.8s ease-out forwards; }
        .hero-title span { background: linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .hero-subtitle { font-size: 1.25rem; color: var(--secondary); margin-bottom: 30px; animation: fadeUp 0.8s ease-out 0.2s forwards; }
        .btn-legado { display: inline-flex; align-items: center; gap: 10px; background: rgba(255, 255, 255, 0.4); border: 1px solid rgba(255,255,255,0.6); padding: 12px 28px; border-radius: 50px; text-decoration: none; color: #475569; font-weight: 600; transition: all 0.3s ease; backdrop-filter: blur(10px); margin-bottom: 50px; animation: fadeUp 0.8s ease-out 0.3s forwards; }
        .btn-legado:hover { background: white; border-color: #d4af37; color: #d4af37; transform: translateY(-3px); }
        .search-container { display: flex; align-items: center; gap: 10px; background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(20px); padding: 8px; border-radius: 50px; box-shadow: 0 20px 40px -10px rgba(0,0,0,0.08); border: 1px solid white; width: fit-content; margin: 0 auto 60px; animation: fadeUp 0.8s ease-out 0.4s forwards; transition: transform 0.3s; }
        .search-container:hover { transform: translateY(-5px); }
        .city-select { border: none; background: transparent; padding: 12px 20px; font-family: var(--font-main); font-size: 1rem; color: var(--primary); font-weight: 600; outline: none; cursor: pointer; min-width: 200px; }
        .btn-geo { width: 48px; height: 48px; border-radius: 50%; border: none; background: var(--primary); color: white; font-size: 1.2rem; cursor: pointer; transition: 0.3s; display: flex; align-items: center; justify-content: center; }
        .btn-geo:hover { background: var(--accent); transform: rotate(15deg); }
        .grid-wrapper { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 30px; max-width: 1100px; margin: 0 auto; padding: 0 20px 100px; }
        .salon-card { background: white; border-radius: 28px; padding: 25px; box-shadow: 0 10px 30px -5px rgba(0,0,0,0.03); text-decoration: none; color: inherit; transition: all 0.4s cubic-bezier(0.2, 0.8, 0.2, 1); border: 1px solid rgba(255,255,255,0.8); position: relative; overflow: hidden; display: block; animation: fadeUp 0.6s ease-out forwards; }
        .salon-card:hover { transform: translateY(-10px) scale(1.02); box-shadow: 0 25px 50px -10px rgba(0,0,0,0.08); z-index: 10; }
        .salon-card.hidden { display: none; }
        .card-header { display: flex; align-items: center; gap: 15px; margin-bottom: 15px; }
        .salon-avatar { width: 60px; height: 60px; background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%); border-radius: 18px; display: flex; align-items: center; justify-content: center; font-weight: 800; color: var(--primary); font-size: 1.8rem; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 1px solid #fff; }
        .salon-info h3 { margin: 0; font-size: 1.2rem; font-weight: 800; color: var(--primary); }
        .salon-info span { font-size: 0.85rem; color: #94a3b8; font-weight: 600; }
        .address { font-size: 0.95rem; color: var(--secondary); margin-bottom: 12px; line-height: 1.5; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .status-pill { font-size: 0.75rem; font-weight: 800; padding: 8px 16px; border-radius: 30px; display: inline-flex; align-items: center; gap: 8px; }
        .status-pill.open { background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
        .status-pill.open::before { content:''; width:8px; height:8px; background:#16a34a; border-radius:50%; }
        .status-pill.closed-online { background: #f3e8ff; color: #7e22ce; border: 1px solid #e9d5ff; }
        .social-row { display: flex; gap: 10px; margin-bottom: 20px; }
        .social-icon { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: #f1f5f9; color: var(--secondary); font-size: 0.95rem; transition: 0.2s; text-decoration: none; border: 1px solid #e2e8f0; }
        .social-icon:hover { background: var(--primary); color: white; border-color: var(--primary); transform: translateY(-3px); }
        .social-icon.instagram:hover { background: #E1306C; border-color: #E1306C; }
        .social-icon.facebook:hover { background: #1877F2; border-color: #1877F2; }
        .social-icon.tiktok:hover { background: #000000; border-color: #000000; }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
        @media (max-width: 768px) { .hero-title { font-size: 3rem; } .search-container { width: 100%; } .city-select { width: 100%; } .navbar { padding: 15px 20px; } }
    </style>
</head>
<body>
    <div class="ambient-bg"><div class="blob blob-1"></div><div class="blob blob-2"></div><div class="blob blob-3"></div></div>
    <nav class="navbar" id="navbar">
        <a href="https://pasotunja.com" target="_blank" class="brand-pill"><div class="dot"></div> PASO</a>
        {% if request.user.is_authenticated %}
            <a href="{% url 'panel_negocio' %}" class="btn-access">Mi Negocio</a>
        {% else %} 
            <a href="{% url 'landing_saas' %}" class="btn-access">Soy Dueño</a> 
        {% endif %}
    </nav>
    <header>
        <h1 class="hero-title">Tu estilo,<br><span>tu tiempo.</span></h1>
        <p class="hero-subtitle">Reserva en los mejores salones y barberías cerca de ti.<br>Sin llamadas, sin esperas.</p>
        <a href="https://pasotunja.com/nuestro-legado/?v=9d69c558f982" target="_blank" class="btn-legado">📖 Conoce nuestro legado</a>
        <div class="search-container">
            <select id="city-selector" class="city-select" onchange="filtrarCiudad(this.value)">
                <option value="">🌎 Ver todas las ciudades</option>
                {% for c in ciudades %}<option value="{{ c }}">📍 {{ c }}</option>{% endfor %}
            </select>
            <button class="btn-geo" onclick="usarUbicacion()" title="Buscar cerca de mí">📍</button>
        </div>
    </header>
    <div class="grid-wrapper" id="salon-grid">
        {% for p in peluquerias %}
            <a href="{% url 'agendar_cita' p.slug %}" class="salon-card" data-lat="{{ p.latitud|default:'0' }}" data-lon="{{ p.longitud|default:'0' }}" data-ciudad="{{ p.ciudad|default:'General' }}">
                <div class="card-header">
                    <div class="salon-avatar">{{ p.name|first|upper }}</div>
                    <div class="salon-info"><h3>{{ p.name }}</h3><span>{{ p.ciudad|default:"Tunja" }}</span></div>
                </div>
                <p class="address">{{ p.address|default:"Ubicación pendiente" }}</p>
                {% if p.instagram or p.facebook or p.tiktok %}
                <div class="social-row" onclick="event.stopPropagation();"> 
                    {% if p.instagram %} <object><a href="{{ p.instagram }}" target="_blank" class="social-icon instagram" title="Instagram"><i class="fab fa-instagram"></i></a></object> {% endif %}
                    {% if p.facebook %} <object><a href="{{ p.facebook }}" target="_blank" class="social-icon facebook" title="Facebook"><i class="fab fa-facebook-f"></i></a></object> {% endif %}
                    {% if p.tiktok %} <object><a href="{{ p.tiktok }}" target="_blank" class="social-icon tiktok" title="TikTok"><i class="fab fa-tiktok"></i></a></object> {% endif %}
                </div>
                {% endif %}
                <div style="display:flex; justify-content: space-between; align-items: center;">
                    <div style="display:flex; gap:8px;">
                        <div class="status-pill open">ABIERTO</div>
                    </div>
                    <span style="font-size:1.2rem; color:#cbd5e1;">→</span>
                </div>
            </a>
        {% empty %}
            <div style="grid-column: 1/-1; text-align: center; padding: 60px; color: #94a3b8;">
                <div style="font-size: 3rem; margin-bottom: 20px;">☕</div>
                <p>No hay salones registrados aún. ¡Registra el tuyo en "Soy Dueño"!</p>
            </div>
        {% endfor %}
    </div>
    <footer>&copy; 2026 PASO Manager. Todos los derechos reservados.</footer>
    <script>
        window.addEventListener('scroll', () => { document.getElementById('navbar').classList.toggle('scrolled', window.scrollY > 20); });
        function filtrarCiudad(ciudad) { document.querySelectorAll('.salon-card').forEach(card => { if (ciudad === "" || card.dataset.ciudad === ciudad) card.classList.remove('hidden'); else card.classList.add('hidden'); }); }
        function usarUbicacion() {
            if(!navigator.geolocation) { alert("GPS no soportado."); return; }
            navigator.geolocation.getCurrentPosition(pos => {
                const myLat = pos.coords.latitude, myLon = pos.coords.longitude;
                let count = 0; document.getElementById('city-selector').value = ""; 
                document.querySelectorAll('.salon-card').forEach(card => {
                    const lat = parseFloat(card.dataset.lat) || 0; const lon = parseFloat(card.dataset.lon) || 0;
                    if (lat === 0 || lon === 0) return; 
                    const dist = getDistance(myLat, myLon, lat, lon);
                    if(dist <= 2.5) { card.classList.remove('hidden'); count++; } else { card.classList.add('hidden'); }
                });
                if(count === 0) alert("No encontramos salones a menos de 2.5km de tu ubicación actual.");
            }, () => alert("Necesitamos permiso de ubicación para mostrarte salones cercanos."));
        }
        function getDistance(lat1, lon1, lat2, lon2) {
            const R = 6371; const dLat = (lat2-lat1)*Math.PI/180; const dLon = (lon2-lon1)*Math.PI/180;
            const a = Math.sin(dLat/2)*Math.sin(dLat/2) + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)* Math.sin(dLon/2)*Math.sin(dLon/2);
            return R * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
        }
    </script>
</body>
</html>
"""
with open('salon/templates/salon/index.html', 'w', encoding='utf-8') as f:
    f.write(html_code)

print("✅ Index.html actualizado con TU diseño.")


# 2. ADAPTAR EL MODELO PARA QUE TENGA LOS CAMPOS QUE PIDE TU HTML
# (Añadimos ciudad, redes sociales, latitud, etc.)
models_code = """from django.db import models
from django.contrib.auth.models import User
import uuid

class Tenant(models.Model):
    users = models.ManyToManyField(User, related_name='tenants')
    name = models.CharField(max_length=100, verbose_name="Nombre del Salón")
    subdomain = models.CharField(max_length=100, unique=True, verbose_name="Identificador (Slug)")
    address = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # CAMPOS NUEVOS PARA TU DISEÑO
    ciudad = models.CharField(max_length=100, default="Tunja")
    latitud = models.FloatField(default=0.0)
    longitud = models.FloatField(default=0.0)
    instagram = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    tiktok = models.URLField(blank=True)
    
    # Configuración de Pagos
    nequi_number = models.CharField(max_length=20, blank=True, verbose_name="Nequi del Negocio")
    bold_api_key = models.CharField(max_length=200, blank=True, verbose_name="Api Key Bold")
    
    created_at = models.DateTimeField(auto_now_add=True)

    # PROPIEDAD MAGICA: Tu HTML pide 'p.slug', nosotros tenemos 'subdomain'.
    # Esto hace que funcionen igual.
    @property
    def slug(self):
        return self.subdomain

    def __str__(self): return self.name

class Professional(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    photo = models.ImageField(upload_to='profesionales/', blank=True, null=True)
    is_external = models.BooleanField(default=False)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    payment_info = models.TextField(blank=True)
    telegram_chat_id = models.CharField(max_length=50, blank=True, null=True)
    invite_token = models.UUIDField(default=uuid.uuid4, editable=False)
    balance_due = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    def __str__(self): return self.name

class Service(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_min = models.IntegerField(default=30)
    def __str__(self): return f"{self.name} - ${self.price}"

class Product(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    def __str__(self): return self.name

class Appointment(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=20)
    date = models.DateField()
    time = models.TimeField()
    status = models.CharField(max_length=20, default='PENDING')
    is_delivery = models.BooleanField(default=False)
    address_delivery = models.TextField(blank=True, null=True)
    def __str__(self): return f"{self.customer_name} - {self.status}"

class ExternalPayment(models.Model):
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_paid = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
"""
with open('salon/models.py', 'w', encoding='utf-8') as f:
    f.write(models_code)
print("✅ Models.py actualizado (Ahora soporta ciudades y redes sociales).")


# 3. CONECTAR LOS ENLACES (URLS.PY) PARA QUE COINCIDAN CON TU HTML
urls_code = """from django.urls import path, include
from . import views

urlpatterns = [
    # Portada (Tu Diseño)
    path('', views.public_home, name='home'),
    
    # Enlaces que pide tu HTML:
    path('accounts/login/', views.custom_login, name='landing_saas'), # 'Soy Dueño' va al login
    path('dashboard/', views.dashboard, name='panel_negocio'),        # 'Mi Negocio' va al dashboard
    path('reservar/<slug:slug>/', views.booking_page, name='agendar_cita'), # Clic en tarjeta de peluquería
    path('mi-agenda/', views.client_agenda, name='mi_agenda'),        # 'Mi Agenda' (Cliente)

    # Rutas internas
    path('accounts/', include('django.contrib.auth.urls')),
    path('settings/', views.settings_view, name='settings'),
    path('inventory/', views.inventory_list, name='inventory'),
    path('inventory/add/', views.add_product, name='add_product'),
    path('invite-pro/', views.invite_external, name='invite_external'),
    path('register-external/<uuid:token>/', views.register_external_view, name='register_external'),
    path('pay-pro/<int:pro_id>/', views.pay_external, name='pay_external'),
]
"""
with open('salon/urls.py', 'w', encoding='utf-8') as f:
    f.write(urls_code)
print("✅ Urls.py sincronizado con los nombres de tu HTML (panel_negocio, landing_saas, etc).")


# 4. ACTUALIZAR VISTAS PARA QUE TODO FUNCIONE
views_code = """from django.shortcuts import render, redirect, get_object_or_404
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
"""
with open('salon/views.py', 'w', encoding='utf-8') as f:
    f.write(views_code)
print("✅ Views.py reparado para alimentar tu diseño con datos reales.")

# 5. CREAR ARCHIVOS VACIOS QUE FALTAN PARA QUE NO DE ERROR
os.makedirs('salon/templates/salon', exist_ok=True)
with open('salon/templates/salon/agendar.html', 'w') as f: f.write("<h1>Página de Agendamiento (En construcción)</h1>")
with open('salon/templates/salon/mi_agenda.html', 'w') as f: f.write("<h1>Agenda del Cliente (En construcción)</h1>")

print("--- TODO LISTO ---")
