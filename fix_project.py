import os

# 1. MODELOS: Bold Simple, Nequi y Telegram Detallado
models_code = """from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify
from django.utils import timezone
import requests
import pytz 

class ConfiguracionPlataforma(models.Model):
    solo_un_registro = models.CharField(max_length=1, default='X', editable=False)
    link_pago_bold = models.URLField("Link Respaldo", default="https://checkout.bold.co/payment/LNK_QZ5NWWY82P")
    bold_secret_key = models.CharField(max_length=255, blank=True, null=True)
    telegram_token = models.CharField(max_length=255, blank=True)
    telegram_chat_id = models.CharField(max_length=255, blank=True)
    precio_mensualidad = models.IntegerField(default=130000)
    class Meta: verbose_name_plural = "Configuración Dueño PASO"
    def __str__(self): return "Configuración Plataforma"

class Peluqueria(models.Model):
    nombre = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    nombre_visible = models.CharField(max_length=200, default="Mi Salón")
    ciudad = models.CharField(max_length=100, default="Tunja")
    direccion = models.CharField(max_length=200, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    codigo_pais_wa = models.CharField(max_length=5, default="57")
    porcentaje_abono = models.IntegerField(default=50)
    bold_api_key = models.CharField("Llave de Identidad", max_length=255, blank=True, null=True)
    bold_secret_key = models.CharField("Llave Secreta", max_length=255, blank=True, null=True)
    nequi_celular = models.CharField(max_length=20, blank=True, null=True)
    nequi_qr_imagen = models.ImageField(upload_to='qrs_nequi/', blank=True, null=True)
    fecha_inicio_contrato = models.DateTimeField(default=timezone.now)
    activo_saas = models.BooleanField(default=True)
    telegram_token = models.CharField(max_length=200, blank=True, null=True)
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True)
    hora_apertura = models.TimeField(default="08:00")
    hora_cierre = models.TimeField(default="20:00")
    latitud = models.FloatField(default=5.5353)
    longitud = models.FloatField(default=-73.3678)
    @property
    def acepta_pagos_digitales(self): return bool(self.bold_secret_key) or bool(self.nequi_celular)
    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)
    def __str__(self): return self.nombre_visible

class Servicio(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='servicios')
    nombre = models.CharField(max_length=100)
    duracion = models.DurationField()
    precio = models.IntegerField()
    @property
    def str_duracion(self):
        ts = int(self.duracion.total_seconds())
        return f"{ts//3600}h {(ts%3600)//60}m" if ts//3600 > 0 else f"{(ts%3600)//60} min"
    def __str__(self): return f"{self.nombre} - ${self.precio}"

class Empleado(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='empleados')
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='empleado_perfil')
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    email_contacto = models.EmailField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    def __str__(self): return f"{self.nombre} {self.apellido}"

DIAS = ((0,'L'),(1,'M'),(2,'X'),(3,'J'),(4,'V'),(5,'S'),(6,'D'))
class HorarioEmpleado(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='horarios')
    dia_semana = models.IntegerField(choices=DIAS)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    almuerzo_inicio = models.TimeField(blank=True, null=True)
    almuerzo_fin = models.TimeField(blank=True, null=True)
    class Meta: unique_together = ('empleado', 'dia_semana')

class Ausencia(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='ausencias')
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    motivo = models.CharField(max_length=200, blank=True)
    creado_en = models.DateTimeField(default=timezone.now)

class Cita(models.Model):
    ESTADOS = [('P', 'Pendiente'), ('C', 'Confirmada'), ('X', 'Cancelada')]
    METODOS = [('BOLD', 'Bold'), ('NEQUI', 'Nequi'), ('SITIO', 'En Sitio')]
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='citas')
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)
    servicios = models.ManyToManyField(Servicio)
    cliente_nombre = models.CharField(max_length=150)
    cliente_telefono = models.CharField(max_length=20)
    fecha_hora_inicio = models.DateTimeField()
    fecha_hora_fin = models.DateTimeField()
    precio_total = models.IntegerField(default=0)
    abono_pagado = models.IntegerField(default=0)
    metodo_pago = models.CharField(max_length=10, choices=METODOS, default='SITIO')
    referencia_pago = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=1, choices=ESTADOS, default='C')
    creado_en = models.DateTimeField(auto_now_add=True)
    @property
    def saldo_pendiente(self): return self.precio_total - self.abono_pagado
    def enviar_notificacion_telegram(self):
        try:
            if self.peluqueria.telegram_token and self.peluqueria.telegram_chat_id:
                servicios_str = ", ".join([s.nombre for s in self.servicios.all()])
                total_fmt = "{:,.0f}".format(self.precio_total).replace(",", ".")
                abono_fmt = "{:,.0f}".format(self.abono_pagado).replace(",", ".")
                saldo_fmt = "{:,.0f}".format(self.saldo_pendiente).replace(",", ".")
                fecha_fmt = self.fecha_hora_inicio.strftime("%d/%m/%Y %I:%M %p")
                msg = (f"🔥 *NUEVA CITA CONFIRMADA*\\n📅 *Fecha:* {fecha_fmt}\\n👤 *Cliente:* {self.cliente_nombre}\\n"
                       f"📞 *Tel:* {self.cliente_telefono}\\n💇 *Staff:* {self.empleado.nombre}\\n\\n"
                       f"📋 *Servicios:* {servicios_str}\\n💰 *Total:* ${total_fmt}\\n"
                       f"💳 *Abono ({self.metodo_pago}):* ${abono_fmt}\\n📉 *Resta por cobrar:* ${saldo_fmt}")
                requests.post(f"https://api.telegram.org/bot{self.peluqueria.telegram_token}/sendMessage", 
                              data={"chat_id": self.peluqueria.telegram_chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=5)
        except Exception as e: print(f"Error Telegram: {e}")

class Cupon(models.Model):
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.CASCADE, related_name='cupones')
    codigo = models.CharField(max_length=50)
    porcentaje_descuento = models.IntegerField(default=10)
    activo = models.BooleanField(default=True)
    usos_restantes = models.IntegerField(default=100)

class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    peluqueria = models.ForeignKey(Peluqueria, on_delete=models.SET_NULL, null=True, blank=True)
    es_dueño = models.BooleanField(default=False)

class SolicitudSaaS(models.Model):
    nombre_contacto = models.CharField(max_length=100)
    nombre_empresa = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    nichos = models.CharField(max_length=50)
    cantidad_empleados = models.CharField(max_length=50)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    atendido = models.BooleanField(default=False)

@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created: PerfilUsuario.objects.get_or_create(user=instance)
"""

# 2. VISTAS: Panel Dueño, Citas y Test Telegram
views_code = """import logging, json, requests
from datetime import timedelta, time, datetime
from dateutil.relativedelta import relativedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify 
from django.urls import reverse
from .models import Peluqueria, Servicio, Empleado, Cita, HorarioEmpleado, Cupon, ConfiguracionPlataforma, Ausencia
from .forms import ServicioForm, RegistroPublicoEmpleadoForm, AusenciaForm
from .services import obtener_bloques_disponibles
from salon.utils.booking_lock import BookingManager

logger = logging.getLogger(__name__)

def login_custom(request):
    if request.user.is_authenticated: return redirigir_segun_rol(request.user)
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('email'), password=request.POST.get('password'))
        if user: login(request, user); return redirigir_segun_rol(user)
        else: return render(request, 'salon/login.html', {'error': 'Credenciales incorrectas'})
    return render(request, 'salon/login.html')

def redirigir_segun_rol(user):
    if user.is_superuser: return redirect('/admin/')
    try:
        if hasattr(user, 'perfil') and user.perfil.es_dueño: return redirect('panel_negocio')
    except: pass
    try:
        if hasattr(user, 'empleado_perfil'): return redirect('mi_agenda')
    except: pass
    return redirect('inicio')

def logout_view(request): logout(request); return redirect('inicio')

def landing_saas(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                if User.objects.filter(username=request.POST.get('email')).exists(): raise ValueError("El correo ya está registrado.")
                user = User.objects.create_user(username=request.POST.get('username_owner', request.POST.get('email')), email=request.POST.get('email'), password=request.POST.get('password'), first_name=request.POST.get('nombre_owner'), last_name=request.POST.get('apellido_owner'))
                slug = slugify(request.POST.get('nombre_negocio'))
                if Peluqueria.objects.filter(slug=slug).exists(): slug += f"-{int(datetime.now().timestamp())}"
                peluqueria = Peluqueria.objects.create(nombre=request.POST.get('nombre_negocio'), slug=slug, telefono=request.POST.get('telefono', ''), fecha_inicio_contrato=timezone.now())
                user.perfil.peluqueria = peluqueria; user.perfil.es_dueño = True; user.perfil.save()
                Empleado.objects.create(user=user, peluqueria=peluqueria, nombre=user.first_name, apellido=user.last_name, email_contacto=user.email, activo=True)
            config = ConfiguracionPlataforma.objects.first()
            if config and config.telegram_token:
                try: requests.post(f"https://api.telegram.org/bot{config.telegram_token}/sendMessage", data={"chat_id": config.telegram_chat_id, "text": f"💰 *NUEVO SAAS*\\nNegocio: {peluqueria.nombre}", "parse_mode": "Markdown"}, timeout=3)
                except: pass
            login(request, user); return redirect('pago_suscripcion_saas')
        except Exception as e: messages.error(request, f"Error: {str(e)}")
    return render(request, 'salon/landing_saas.html')

@login_required
def pago_suscripcion_saas(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    config = ConfiguracionPlataforma.objects.first()
    monto = config.precio_mensualidad if config else 130000
    if request.method == 'POST':
        if config and config.bold_secret_key:
            try:
                ref = f"SUB-{peluqueria.id}-{int(datetime.now().timestamp())}"
                url = "https://integrations.api.bold.co/online/link/v1"
                headers = {"Authorization": f"x-api-key {config.bold_secret_key}", "Content-Type": "application/json"}
                payload = {"name": "Suscripción PASO", "description": f"Plan Mensual {peluqueria.nombre}", "amount": monto, "currency": "COP", "sku": ref, "expiration_date": (datetime.now() + timedelta(days=1)).isoformat(), "redirection_url": request.build_absolute_uri(reverse('panel_negocio'))}
                r = requests.post(url, json=payload, headers=headers, timeout=10)
                if r.status_code == 201: return redirect(r.json()["payload"]["url"])
            except: pass
        return redirect(config.link_pago_bold) if config else redirect('panel_negocio')
    return render(request, 'salon/pago_suscripcion.html', {'monto': monto, 'peluqueria': peluqueria})

@login_required
def panel_negocio(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = request.user.perfil.peluqueria
    hoy = timezone.localdate()
    inicio = peluqueria.fecha_inicio_contrato.date()
    proximo = inicio
    while proximo <= hoy: proximo += relativedelta(months=1)
    dias = (proximo - hoy).days
    alerta = f"⚠️ Tu plan vence en {dias} días." if dias <= 5 else None

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'test_telegram':
            token, chat = request.POST.get('telegram_token'), request.POST.get('telegram_chat_id')
            peluqueria.telegram_token = token; peluqueria.telegram_chat_id = chat; peluqueria.save()
            try:
                r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat, "text": "✅ *PASO Manager:* Conexión Exitosa.", "parse_mode": "Markdown"}, timeout=5)
                if r.status_code == 200: messages.success(request, "Mensaje de prueba enviado.")
                else: messages.error(request, "Telegram falló. Revisa token/chat_id.")
            except: messages.error(request, "Error de conexión con Telegram.")
        elif accion == 'guardar_info':
            peluqueria.direccion = request.POST.get('direccion'); peluqueria.telefono = request.POST.get('telefono'); peluqueria.hora_apertura = request.POST.get('hora_apertura'); peluqueria.hora_cierre = request.POST.get('hora_cierre'); peluqueria.save(); messages.success(request, "Información guardada.")
        elif accion == 'guardar_pagos':
            peluqueria.porcentaje_abono = int(request.POST.get('porcentaje_abono') or 50); peluqueria.bold_api_key = request.POST.get('bold_api_key'); peluqueria.bold_secret_key = request.POST.get('bold_secret_key'); peluqueria.nequi_celular = request.POST.get('nequi_celular')
            if 'nequi_qr_imagen' in request.FILES: peluqueria.nequi_qr_imagen = request.FILES['nequi_qr_imagen']
            if request.POST.get('borrar_qr') == 'si': peluqueria.nequi_qr_imagen = None
            peluqueria.save(); messages.success(request, "Pagos actualizados.")
        return redirect('panel_negocio')

    citas_hoy = peluqueria.citas.filter(fecha_hora_inicio__date=hoy).order_by('fecha_hora_inicio')
    citas_futuras = peluqueria.citas.filter(fecha_hora_inicio__gte=timezone.now()).order_by('fecha_hora_inicio')[:20]
    ctx = {'peluqueria': peluqueria, 'alerta_pago': alerta, 'proximo_pago': proximo, 'citas_hoy_count': citas_hoy.count(), 'citas_futuras': citas_futuras, 'empleados': peluqueria.empleados.all(), 'servicios': peluqueria.servicios.all(), 'link_invitacion': request.build_absolute_uri(reverse('registro_empleado', args=[peluqueria.slug]))}
    return render(request, 'salon/dashboard.html', ctx)

@login_required
def gestionar_servicios(request):
    peluqueria = request.user.perfil.peluqueria
    if request.method == 'POST':
        form = ServicioForm(request.POST)
        if form.is_valid():
            nuevo = form.save(commit=False); nuevo.peluqueria = peluqueria; nuevo.duracion = timedelta(minutes=form.cleaned_data['duracion_minutos']); nuevo.save(); messages.success(request, "Servicio creado."); return redirect('gestionar_servicios')
    return render(request, 'salon/panel_dueño/servicios.html', {'servicios': peluqueria.servicios.all(), 'form': ServicioForm(), 'peluqueria': peluqueria})

@login_required
def eliminar_servicio(request, servicio_id):
    get_object_or_404(Servicio, id=servicio_id, peluqueria=request.user.perfil.peluqueria).delete(); return redirect('gestionar_servicios')

@login_required
def gestionar_equipo(request):
    peluqueria = request.user.perfil.peluqueria
    link = request.build_absolute_uri(reverse('registro_empleado', args=[peluqueria.slug]))
    return render(request, 'salon/panel_dueño/equipo.html', {'peluqueria': peluqueria, 'empleados': peluqueria.empleados.all(), 'link_invitacion': link})

@login_required
def mi_agenda(request):
    try: empleado = request.user.empleado_perfil
    except: return redirect('login_custom')
    if request.method == 'POST':
        HorarioEmpleado.objects.filter(empleado=empleado).delete()
        for i in range(7):
            if request.POST.get(f'trabaja_{{i}}'): HorarioEmpleado.objects.create(empleado=empleado, dia_semana=i, hora_inicio=request.POST.get(f'inicio_{{i}}'), hora_fin=request.POST.get(f'fin_{{i}}'), almuerzo_inicio=request.POST.get(f'almuerzo_inicio_{{i}}') or None, almuerzo_fin=request.POST.get(f'almuerzo_fin_{{i}}') or None)
        messages.success(request, "Horario actualizado."); return redirect('mi_agenda')
    horarios = {h.dia_semana: h for h in HorarioEmpleado.objects.filter(empleado=empleado)}
    lista = [{'id': i, 'nombre': n, 'trabaja': horarios.get(i) is not None, 'inicio': horarios.get(i).hora_inicio.strftime('%H:%M') if horarios.get(i) else '09:00', 'fin': horarios.get(i).hora_fin.strftime('%H:%M') if horarios.get(i) else '19:00', 'l_ini': horarios.get(i).almuerzo_inicio.strftime('%H:%M') if (horarios.get(i) and horarios.get(i).almuerzo_inicio) else '', 'l_fin': horarios.get(i).almuerzo_fin.strftime('%H:%M') if (horarios.get(i) and horarios.get(i).almuerzo_fin) else ''} for i, n in {0:'Lunes',1:'Martes',2:'Miércoles',3:'Jueves',4:'Viernes',5:'Sábado',6:'Domingo'}.items()]
    citas = Cita.objects.filter(empleado=empleado, fecha_hora_inicio__gte=datetime.now()).order_by('fecha_hora_inicio')
    return render(request, 'salon/mi_horario.html', {'empleado': empleado, 'dias': lista, 'mis_citas': citas})

@login_required
def gestionar_ausencias(request):
    try: empleado = request.user.empleado_perfil
    except: return redirect('inicio')
    if request.method == 'POST':
        form = AusenciaForm(request.POST)
        if form.is_valid(): a = form.save(commit=False); a.empleado = empleado; a.save(); messages.success(request, "Ausencia guardada."); return redirect('gestionar_ausencias')
    ausencias = Ausencia.objects.filter(empleado=empleado, fecha_fin__gte=timezone.now()).order_by('fecha_inicio')
    return render(request, 'salon/ausencias.html', {'form': AusenciaForm(), 'ausencias': ausencias})

@login_required
def eliminar_ausencia(request, ausencia_id):
    get_object_or_404(Ausencia, id=ausencia_id, empleado__user=request.user).delete(); return redirect('gestionar_ausencias')

def registro_empleado_publico(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    if request.method == 'POST':
        form = RegistroPublicoEmpleadoForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if User.objects.filter(username=data['email']).exists(): return render(request, 'salon/registro_empleado.html', {'peluqueria': peluqueria, 'form': form, 'error': 'Correo ya registrado'})
            with transaction.atomic():
                u = User.objects.create_user(username=data['email'], email=data['email'], password=data['password'], first_name=data['nombre'], last_name=data['apellido']); u.perfil.peluqueria = peluqueria; u.perfil.es_dueño = False; u.perfil.save(); e = Empleado.objects.create(peluqueria=peluqueria, user=u, nombre=data['nombre'], apellido=data['apellido'], email_contacto=data['email'], activo=True)
                for i in range(7): HorarioEmpleado.objects.create(empleado=e, dia_semana=i, hora_inicio=time(9,0), hora_fin=time(19,0))
            login(request, u); return redirect('mi_agenda')
    return render(request, 'salon/registro_empleado.html', {'peluqueria': peluqueria, 'form': RegistroPublicoEmpleadoForm()})

def inicio(request): return render(request, 'salon/index.html', {'peluquerias': Peluqueria.objects.all(), 'ciudades': Peluqueria.objects.values_list('ciudad', flat=True).distinct()})

def agendar_cita(request, slug_peluqueria):
    peluqueria = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    if request.method == 'POST':
        try:
            emp_id, fecha, hora, servs_ids = request.POST.get('empleado'), request.POST.get('fecha_seleccionada'), request.POST.get('hora_seleccionada'), request.POST.getlist('servicios')
            metodo = request.POST.get('metodo_pago', 'SITIO')
            if not (emp_id and fecha and hora and servs_ids): raise ValueError("Datos incompletos")
            servs = Servicio.objects.filter(id__in=servs_ids)
            duracion, precio = sum([s.duracion for s in servs], timedelta()), sum([s.precio for s in servs])
            ini = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
            def _reserva(emp):
                if Ausencia.objects.filter(empleado=emp, fecha_inicio__lt=ini + duracion, fecha_fin__gt=ini).exists(): raise ValueError("Estilista ausente")
                if Cita.objects.filter(empleado=emp, estado__in=['P','C'], fecha_hora_inicio__lt=ini + duracion, fecha_hora_fin__gt=ini).exists(): raise ValueError("Horario ocupado")
                c = Cita.objects.create(peluqueria=peluqueria, empleado=emp, cliente_nombre=request.POST.get('nombre_cliente'), cliente_telefono=request.POST.get('telefono_cliente'), fecha_hora_inicio=ini, fecha_hora_fin=ini + duracion, precio_total=precio, estado='P', metodo_pago=metodo); c.servicios.set(servs); return c
            cita = BookingManager.ejecutar_reserva_segura(emp_id, _reserva)
            if metodo == 'BOLD' and peluqueria.bold_secret_key: return redirect('confirmacion_cita', slug_peluqueria=peluqueria.slug, cita_id=cita.id)
            elif metodo == 'NEQUI' and peluqueria.nequi_celular: cita.enviar_notificacion_telegram(); return render(request, 'salon/pago_nequi.html', {'cita': cita, 'peluqueria': peluqueria})
            else: cita.estado = 'C'; cita.save(); cita.enviar_notificacion_telegram(); return render(request, 'salon/confirmacion.html', {'cita': cita})
        except Exception as e: return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': peluqueria.servicios.all(), 'empleados': peluqueria.empleados.filter(activo=True), 'error_mensaje': str(e)})
    return render(request, 'salon/agendar.html', {'peluqueria': peluqueria, 'servicios': peluqueria.servicios.all(), 'empleados': peluqueria.empleados.filter(activo=True), 'tiene_bold': bool(peluqueria.bold_secret_key), 'tiene_nequi': bool(peluqueria.nequi_celular)})

def confirmacion_cita(request, slug_peluqueria, cita_id):
    cita = get_object_or_404(Cita, id=cita_id); peluqueria = cita.peluqueria
    if not peluqueria.bold_secret_key: return render(request, 'salon/confirmacion.html', {'cita': cita, 'mensaje': 'Pago en sitio'})
    try:
        ref = f"CITA-{cita.id}-{int(datetime.now().timestamp())}"
        abono = int(cita.precio_total * (peluqueria.porcentaje_abono/100))
        url = "https://integrations.api.bold.co/online/link/v1"
        headers = {"Authorization": f"x-api-key {peluqueria.bold_secret_key}", "Content-Type": "application/json"}
        payload = {"name": f"Reserva Cita #{cita.id}", "description": "Abono servicio", "amount": abono, "currency": "COP", "sku": ref, "redirection_url": request.build_absolute_uri(reverse('retorno_bold'))}
        r = requests.post(url, json=payload, headers=headers, timeout=8)
        if r.status_code == 201: cita.abono_pagado = abono; cita.referencia_pago = ref; cita.save(); return redirect(r.json()["payload"]["url"])
        else: return render(request, 'salon/confirmacion.html', {'cita': cita, 'mensaje': 'Error conectando con Bold. Paga en sitio.'})
    except: return render(request, 'salon/confirmacion.html', {'cita': cita, 'mensaje': 'Error técnico. Paga en sitio.'})

def api_obtener_horarios(request):
    try: return JsonResponse({'horas': obtener_bloques_disponibles(Empleado.objects.get(id=request.GET.get('empleado_id')), datetime.strptime(request.GET.get('fecha'), '%Y-%m-%d').date(), timedelta(minutes=30))})
    except: return JsonResponse({'horas': []})

def retorno_bold(request): return render(request, 'salon/confirmacion.html', {'mensaje': '¡Pago Exitoso! Tu cita ha sido confirmada.'})
"""

# --- 3. HTML DASHBOARD (Diseño Premium + Tabs) ---
dashboard_code = """{% load static %}
<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Panel de Control | PASO</title><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet"><style>:root{--primary:#0f172a;--secondary:#475569;--accent:#db2777;--bg:#f8fafc;--surface:#ffffff;--success:#10b981;--border:#e2e8f0;--telegram:#229ED9;}body{font-family:'Manrope',sans-serif;background:var(--bg);color:var(--primary);margin:0;padding-bottom:40px;}.dashboard-header{background:var(--surface);padding:20px 30px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:50;}.brand{font-weight:800;font-size:1.5rem;display:flex;align-items:center;gap:10px;}.btn-logout{font-size:0.9rem;color:#ef4444;text-decoration:none;font-weight:600;padding:8px 15px;background:#fef2f2;border-radius:8px;}.container{max-width:1100px;margin:30px auto;padding:0 20px;}.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin-bottom:40px;}.stat-card{background:var(--surface);padding:20px;border-radius:16px;border:1px solid var(--border);box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);}.stat-val{font-size:2rem;font-weight:800;color:var(--accent);}.stat-label{color:var(--secondary);font-size:0.9rem;font-weight:600;}.tabs{display:flex;gap:10px;margin-bottom:25px;border-bottom:2px solid var(--border);padding-bottom:10px;overflow-x:auto;}.tab-btn{padding:10px 20px;border:none;background:none;font-weight:600;color:var(--secondary);cursor:pointer;border-radius:8px;transition:0.2s;white-space:nowrap;}.tab-btn.active{background:var(--primary);color:white;}.tab-content{display:none;animation:fadeIn 0.3s;}.tab-content.active{display:block;}.card{background:var(--surface);border-radius:16px;padding:30px;border:1px solid var(--border);margin-bottom:30px;}.form-group{margin-bottom:20px;}label{display:block;font-weight:700;font-size:0.9rem;margin-bottom:8px;color:var(--secondary);}input,select{width:100%;padding:12px;border:1px solid var(--border);border-radius:8px;font-family:inherit;font-size:0.95rem;}.btn-save{background:var(--primary);color:white;border:none;padding:12px 25px;border-radius:8px;font-weight:700;cursor:pointer;width:100%;}.btn-telegram{background:var(--telegram);color:white;border:none;padding:12px 25px;border-radius:8px;font-weight:700;cursor:pointer;width:100%;display:flex;justify-content:center;gap:8px;align-items:center;}.btn-row{display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-top:20px;}.menu-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:15px;}.menu-item{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:25px;background:var(--surface);border:1px solid var(--border);border-radius:12px;text-decoration:none;color:var(--primary);transition:0.2s;font-weight:700;gap:10px;}.menu-item:hover{border-color:var(--accent);transform:translateY(-3px);}.menu-icon{font-size:1.8rem;color:var(--accent);}.pay-config-grid{display:grid;gap:30px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));}.pay-box{background:#f8fafc;padding:20px;border-radius:12px;border:1px solid var(--border);}table{width:100%;border-collapse:collapse;background:white;min-width:600px;}th,td{padding:15px;text-align:left;border-bottom:1px solid var(--border);font-size:0.9rem;}th{background:#f1f5f9;font-weight:700;color:var(--secondary);}.badge{padding:4px 10px;border-radius:20px;font-size:0.75rem;font-weight:700;}.bg-green{background:#dcfce7;color:#166534;}.bg-yellow{background:#fef9c3;color:#854d0e;}@keyframes fadeIn{from{opacity:0;}to{opacity:1;}}</style></head><body><header class="dashboard-header"><div class="brand"><i class="fas fa-cut" style="color:var(--accent);"></i><span>PASO Manager</span></div><a href="{% url 'logout_usuario' %}" class="btn-logout"><i class="fas fa-sign-out-alt"></i> Salir</a></header><div class="container">{% if alerta_pago %}<div style="padding:15px;background:#fff7ed;color:#c2410c;border:1px solid #fdba74;border-radius:10px;margin-bottom:20px;font-weight:600;"><i class="fas fa-exclamation-triangle"></i> {{ alerta_pago }} <a href="{% url 'pago_suscripcion_saas' %}" style="text-decoration:underline;">Pagar</a></div>{% endif %}{% if messages %}{% for message in messages %}<div style="padding:15px;background:#dcfce7;color:#166534;border:1px solid #86efac;border-radius:10px;margin-bottom:20px;"><i class="fas fa-check-circle"></i> {{ message }}</div>{% endfor %}{% endif %}<div class="stats-grid"><div class="stat-card"><div class="stat-val">{{ citas_hoy_count }}</div><div class="stat-label">Citas Hoy</div></div><div class="stat-card"><div class="stat-val">{{ empleados.count }}</div><div class="stat-label">Equipo</div></div><div class="stat-card"><div class="stat-val" style="font-size:1.2rem;">{{ proximo_pago|date:"d M" }}</div><div class="stat-label">Corte</div></div></div><div class="tabs"><button class="tab-btn active" onclick="openTab(event, 'tab-inicio')">🏠 Menú</button><button class="tab-btn" onclick="openTab(event, 'tab-citas')">📅 Gestión Citas</button><button class="tab-btn" onclick="openTab(event, 'tab-config')">⚙️ Configuración</button><button class="tab-btn" onclick="openTab(event, 'tab-pagos')">💳 Pagos</button></div><div id="tab-inicio" class="tab-content active"><div class="menu-grid"><a href="{% url 'gestionar_servicios' %}" class="menu-item"><i class="fas fa-list menu-icon"></i><span>Servicios</span></a><a href="{% url 'gestionar_equipo' %}" class="menu-item"><i class="fas fa-users menu-icon"></i><span>Equipo</span></a><a href="{% url 'mi_agenda' %}" class="menu-item"><i class="fas fa-calendar-alt menu-icon"></i><span>Mi Agenda</span></a><a href="{% url 'pago_suscripcion_saas' %}" class="menu-item"><i class="fas fa-receipt menu-icon"></i><span>Suscripción</span></a></div><div class="card" style="margin-top:30px;padding:20px;background:#eff6ff;"><h3 style="margin-top:0;font-size:1rem;color:#1e3a8a;">🔗 Link Empleados</h3><div style="display:flex;gap:10px;"><input type="text" value="{{ link_invitacion }}" id="linkInput" readonly><button onclick="copiarLink()" class="btn-save" style="width:auto;background:#2563eb;">Copiar</button></div></div></div><div id="tab-citas" class="tab-content"><div class="card"><h2>Próximas Citas</h2><div style="overflow-x:auto;"><table><thead><tr><th>Fecha</th><th>Cliente</th><th>Tel</th><th>Total</th><th>Abono</th><th>Pendiente</th><th>Estado</th></tr></thead><tbody>{% for c in citas_futuras %}<tr><td>{{ c.fecha_hora_inicio|date:"d M, H:i" }}</td><td>{{ c.cliente_nombre }}</td><td>{{ c.cliente_telefono }}</td><td>${{ c.precio_total }}</td><td>${{ c.abono_pagado }} <small>({{ c.metodo_pago }})</small></td><td style="font-weight:bold;color:#db2777;">${{ c.saldo_pendiente }}</td><td>{% if c.estado == 'C' %}<span class="badge bg-green">Confirmada</span>{% else %}<span class="badge bg-yellow">Pendiente</span>{% endif %}</td></tr>{% empty %}<tr><td colspan="7" style="text-align:center;">No hay citas.</td></tr>{% endfor %}</tbody></table></div></div></div><div id="tab-config" class="tab-content"><div class="card"><h2>Datos y Notificaciones</h2><form method="POST">{% csrf_token %}<div class="form-group"><label>Dirección</label><input type="text" name="direccion" value="{{ peluqueria.direccion }}"></div><div class="form-group"><label>Teléfono</label><input type="text" name="telefono" value="{{ peluqueria.telefono }}"></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;"><div class="form-group"><label>Abre</label><input type="time" name="hora_apertura" value="{{ peluqueria.hora_apertura|time:'H:i' }}"></div><div class="form-group"><label>Cierra</label><input type="time" name="hora_cierre" value="{{ peluqueria.hora_cierre|time:'H:i' }}"></div></div><h3 style="margin-top:20px;font-size:1rem;">Telegram Bot</h3><div class="form-group"><label>Token</label><input type="password" name="telegram_token" value="{{ peluqueria.telegram_token|default:'' }}"></div><div class="form-group"><label>Chat ID</label><input type="text" name="telegram_chat_id" value="{{ peluqueria.telegram_chat_id|default:'' }}"></div><div class="btn-row"><button type="submit" name="accion" value="test_telegram" class="btn-telegram"><i class="fab fa-telegram-plane"></i> Probar Bot</button><button type="submit" name="accion" value="guardar_info" class="btn-save"><i class="fas fa-save"></i> Guardar</button></div></form></div></div><div id="tab-pagos" class="tab-content"><div class="card"><h2>Configuración de Cobros</h2><form method="POST" enctype="multipart/form-data">{% csrf_token %}<input type="hidden" name="accion" value="guardar_pagos"><div class="form-group"><label>Porcentaje Abono (%)</label><input type="number" name="porcentaje_abono" value="{{ peluqueria.porcentaje_abono }}" min="0" max="100"></div><div class="pay-config-grid"><div class="pay-box"><span style="font-weight:800;font-size:1.2rem;">BOLD</span><div class="form-group"><label>Llave de Identidad</label><input type="text" name="bold_api_key" value="{{ peluqueria.bold_api_key|default:'' }}"></div><div class="form-group"><label>Llave Secreta</label><input type="password" name="bold_secret_key" value="{{ peluqueria.bold_secret_key|default:'' }}"></div></div><div class="pay-box"><span style="font-weight:800;font-size:1.2rem;">NEQUI</span><div class="form-group"><label>Celular Nequi</label><input type="text" name="nequi_celular" value="{{ peluqueria.nequi_celular|default:'' }}"></div><div class="form-group"><label>QR Imagen</label>{% if peluqueria.nequi_qr_imagen %}<img src="{{ peluqueria.nequi_qr_imagen.url }}" style="max-width:80px;display:block;margin:5px 0;">{% endif %}<input type="file" name="nequi_qr_imagen" accept="image/*"></div></div></div><button type="submit" class="btn-save" style="margin-top:20px;">Guardar Pagos</button></form></div></div></div><script>function openTab(evt,name){document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));document.getElementById(name).classList.add('active');evt.currentTarget.classList.add('active');}function copiarLink(){var c=document.getElementById("linkInput");c.select();navigator.clipboard.writeText(c.value);alert("Link copiado!");}</script></body></html>
"""

# --- 4. ESCRIBIR ARCHIVOS ---
with open('salon/models.py', 'w', encoding='utf-8') as f: f.write(models_code)
with open('salon/views.py', 'w', encoding='utf-8') as f: f.write(views_code)
with open('salon/templates/salon/dashboard.html', 'w', encoding='utf-8') as f: f.write(dashboard_code)

print("✅ Archivos reparados y actualizados correctamente.")
