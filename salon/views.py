import logging, json, requests
from datetime import timedelta, time, datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify 
from django.urls import reverse
from django.http import JsonResponse
from .models import Peluqueria, Servicio, Empleado, Cita, HorarioEmpleado, ConfiguracionPlataforma, Ausencia, Producto, MovimientoInventario, PerfilUsuario
from .forms import ServicioForm, RegistroPublicoEmpleadoForm, AusenciaForm
from .services import obtener_bloques_disponibles
from salon.utils.booking_lock import BookingManager

def asegurar_slug(peluqueria):
    if not peluqueria.slug: peluqueria.slug = slugify(peluqueria.nombre) or f"salon-{peluqueria.id}"; peluqueria.save()
    return peluqueria

def login_custom(request):
    if request.user.is_authenticated: return redirigir_segun_rol(request.user)
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('email'), password=request.POST.get('password'))
        if user: login(request, user); return redirigir_segun_rol(user)
        else: return render(request, 'salon/login.html', {'error': 'Credenciales incorrectas'})
    return render(request, 'salon/login.html')

def redirigir_segun_rol(user):
    if user.is_superuser: return redirect('/admin/')
    if hasattr(user, 'perfil') and user.perfil.es_dueño: return redirect('panel_negocio')
    if hasattr(user, 'empleado_perfil'): return redirect('mi_agenda')
    return redirect('inicio')

def logout_view(request): logout(request); return redirect('inicio')

def landing_saas(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                email = request.POST.get('email')
                if User.objects.filter(username=email).exists(): raise ValueError("Correo usado.")
                user = User.objects.create_user(username=email, email=email, password=request.POST.get('password'), first_name=request.POST.get('nombre_owner'), last_name=request.POST.get('apellido_owner'))
                slug = slugify(request.POST.get('nombre_negocio')) or f"negocio-{int(datetime.now().timestamp())}"
                p = Peluqueria.objects.create(nombre=request.POST.get('nombre_negocio'), slug=slug, telefono=request.POST.get('telefono', ''), fecha_inicio_contrato=timezone.now())
                PerfilUsuario.objects.create(user=user, peluqueria=p, es_dueño=True)
                Empleado.objects.create(user=user, peluqueria=p, nombre=user.first_name, apellido=user.last_name, email_contacto=user.email, activo=True)
            login(request, user); return redirect('pago_suscripcion_saas')
        except Exception as e: messages.error(request, str(e))
    return render(request, 'salon/landing_saas.html')

@login_required
def pago_suscripcion_saas(request):
    if not request.user.perfil.es_dueño: return redirect('inicio')
    return redirect('panel_negocio') # Simplificado para demo

@login_required
def panel_negocio(request):
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_dueño: return redirect('inicio')
    peluqueria = asegurar_slug(request.user.perfil.peluqueria)
    
    if request.method == 'POST':
        try:
            accion = request.POST.get('accion')
            if accion == 'guardar_general':
                peluqueria.nombre_visible = request.POST.get('nombre_visible')
                peluqueria.ciudad = request.POST.get('ciudad')
                peluqueria.direccion = request.POST.get('direccion')
                peluqueria.telefono = request.POST.get('telefono')
                peluqueria.instagram = request.POST.get('instagram')
                peluqueria.facebook = request.POST.get('facebook')
                peluqueria.tiktok = request.POST.get('tiktok')
            elif accion == 'guardar_pagos':
                peluqueria.porcentaje_abono = int(request.POST.get('porcentaje_abono') or 50)
                peluqueria.bold_api_key = request.POST.get('bold_api_key')
                peluqueria.bold_secret_key = request.POST.get('bold_secret_key')
                peluqueria.nequi_celular = request.POST.get('nequi_celular')
                peluqueria.ofrece_domicilio = request.POST.get('ofrece_domicilio') == 'on'
                peluqueria.comision_domicilio = int(request.POST.get('comision_domicilio') or 10)
            elif accion == 'guardar_notificaciones':
                peluqueria.telegram_token = request.POST.get('telegram_token')
                peluqueria.telegram_chat_id = request.POST.get('telegram_chat_id')
            peluqueria.save(); messages.success(request, "Guardado.")
        except Exception as e: messages.error(request, str(e))
        return redirect('panel_negocio')

    ctx = {'peluqueria': peluqueria, 'citas_hoy_count': peluqueria.citas.filter(fecha_hora_inicio__date=timezone.localdate()).count(), 'empleados': peluqueria.empleados.all(), 'inventario_count': peluqueria.inventario.count()}
    return render(request, 'salon/dashboard.html', ctx)

@login_required
def confirmar_pago_manual(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id, peluqueria=request.user.perfil.peluqueria)
    if cita.estado == 'P':
        cita.estado = 'C'
        cita.abono_pagado = int(cita.precio_total * (cita.peluqueria.porcentaje_abono/100))
        cita.save()
        for s in cita.servicios.all():
            if s.producto_asociado: s.producto_asociado.cantidad_actual -= s.cantidad_descuento; s.producto_asociado.save()
        messages.success(request, "Pago confirmado.")
    return redirect('panel_negocio')

@login_required
def gestionar_inventario(request):
    p = request.user.perfil.peluqueria
    if request.method == 'POST':
        if request.POST.get('accion') == 'nuevo_producto':
            Producto.objects.create(peluqueria=p, nombre=request.POST.get('nombre'), costo_compra=request.POST.get('costo') or 0, precio_venta=request.POST.get('precio') or 0, cantidad_actual=request.POST.get('cantidad') or 0, stock_minimo=request.POST.get('minimo') or 5, es_insumo_interno=request.POST.get('es_insumo')=='on')
        elif request.POST.get('accion') == 'registrar_venta':
            pr = get_object_or_404(Producto, id=request.POST.get('producto_id'), peluqueria=p)
            cnt = int(request.POST.get('cantidad'))
            if pr.cantidad_actual >= cnt: pr.cantidad_actual -= cnt; pr.save(); MovimientoInventario.objects.create(producto=pr, tipo='SALIDA', cantidad=cnt); messages.success(request, "Venta OK.")
    return render(request, 'salon/panel_dueño/inventario.html', {'peluqueria': p, 'productos': p.inventario.all()})

@login_required
def gestionar_servicios(request):
    p = request.user.perfil.peluqueria
    if request.method == 'POST':
        form = ServicioForm(request.POST)
        if form.is_valid(): n=form.save(commit=False); n.peluqueria=p; n.duracion=timedelta(minutes=form.cleaned_data['duracion_minutos']); n.producto_asociado_id=request.POST.get('producto_asociado'); n.save(); return redirect('gestionar_servicios')
    return render(request, 'salon/panel_dueño/servicios.html', {'servicios': p.servicios.all(), 'form': ServicioForm(), 'peluqueria': p, 'productos': p.inventario.all()})

@login_required
def eliminar_servicio(request, servicio_id): get_object_or_404(Servicio, id=servicio_id, peluqueria=request.user.perfil.peluqueria).delete(); return redirect('gestionar_servicios')

@login_required
def gestionar_equipo(request):
    p = asegurar_slug(request.user.perfil.peluqueria)
    if request.method == 'POST':
        e = get_object_or_404(Empleado, id=request.POST.get('empleado_id'), peluqueria=p)
        e.es_independiente = request.POST.get('es_independiente') == 'on'
        e.save(); messages.success(request, "Actualizado.")
        return redirect('gestionar_equipo')
    return render(request, 'salon/panel_dueño/equipo.html', {'peluqueria': p, 'empleados': p.empleados.all(), 'link_invitacion': request.build_absolute_uri(reverse('registro_empleado', args=[p.slug]))})

@login_required
def mi_agenda(request):
    try: e = request.user.empleado_perfil
    except: return redirect('login_custom')
    if request.method == 'POST':
        if 'config_independiente' in request.POST:
            e.instagram = request.POST.get('instagram')
            if e.es_independiente: e.bold_api_key=request.POST.get('bold_api_key'); e.bold_secret_key=request.POST.get('bold_secret_key'); e.telegram_token=request.POST.get('telegram_token'); e.telegram_chat_id=request.POST.get('telegram_chat_id')
            e.save()
        else:
            HorarioEmpleado.objects.filter(empleado=e).delete()
            for i in range(7):
                if request.POST.get(f'trabaja_{i}'): HorarioEmpleado.objects.create(empleado=e, dia_semana=i, hora_inicio=request.POST.get(f'inicio_{i}'), hora_fin=request.POST.get(f'fin_{i}'), almuerzo_inicio=request.POST.get(f'almuerzo_inicio_{i}') or None, almuerzo_fin=request.POST.get(f'almuerzo_fin_{i}') or None)
        return redirect('mi_agenda')
    h = {x.dia_semana: x for x in HorarioEmpleado.objects.filter(empleado=e)}
    dias = [{'id': i, 'nombre': n, 'trabaja': h.get(i)} for i, n in enumerate(['L','M','X','J','V','S','D'])]
    return render(request, 'salon/mi_horario.html', {'empleado': e, 'dias': dias, 'mis_citas': Cita.objects.filter(empleado=e, fecha_hora_inicio__gte=datetime.now())})

@login_required
def gestionar_ausencias(request):
    try: e = request.user.empleado_perfil
    except: return redirect('inicio')
    if request.method == 'POST':
        f = AusenciaForm(request.POST)
        if f.is_valid(): a=f.save(commit=False); a.empleado=e; a.save(); return redirect('gestionar_ausencias')
    return render(request, 'salon/ausencias.html', {'form': AusenciaForm(), 'ausencias': Ausencia.objects.filter(empleado=e)})

@login_required
def eliminar_ausencia(request, ausencia_id): get_object_or_404(Ausencia, id=ausencia_id, empleado__user=request.user).delete(); return redirect('gestionar_ausencias')

def registro_empleado_publico(request, slug_peluqueria):
    p = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    if request.method == 'POST':
        f = RegistroPublicoEmpleadoForm(request.POST)
        if f.is_valid():
            d = f.cleaned_data
            if User.objects.filter(username=d['email']).exists(): return render(request, 'salon/registro_empleado.html', {'error': 'Correo usado'})
            with transaction.atomic():
                u = User.objects.create_user(username=d['email'], email=d['email'], password=d['password'], first_name=d['nombre'], last_name=d['apellido'])
                e = Empleado.objects.create(peluqueria=p, user=u, nombre=d['nombre'], apellido=d['apellido'], email_contacto=d['email'], activo=True)
                for i in range(7): HorarioEmpleado.objects.create(empleado=e, dia_semana=i, hora_inicio=time(9,0), hora_fin=time(19,0))
            login(request, u); return redirect('mi_agenda')
    return render(request, 'salon/registro_empleado.html', {'peluqueria': p, 'form': RegistroPublicoEmpleadoForm()})

def inicio(request): return render(request, 'salon/index.html', {'peluquerias': Peluqueria.objects.filter(activo_saas=True), 'ciudades': Peluqueria.objects.values_list('ciudad', flat=True).distinct()})

def agendar_cita(request, slug_peluqueria):
    p = get_object_or_404(Peluqueria, slug=slug_peluqueria)
    if request.method == 'POST':
        try:
            if not request.POST.get('acepta_politicas'): raise ValueError("Acepta políticas.")
            emp_id = request.POST.get('empleado'); fecha = request.POST.get('fecha_seleccionada'); hora = request.POST.get('hora_seleccionada'); servs_ids = request.POST.getlist('servicios')
            if not (emp_id and fecha and hora and servs_ids): raise ValueError("Faltan datos.")
            servs = Servicio.objects.filter(id__in=servs_ids)
            ini = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
            
            def _crear(emp):
                fin = ini + sum([s.duracion for s in servs], timedelta())
                if Ausencia.objects.filter(empleado=emp, fecha_inicio__lt=fin, fecha_fin__gt=ini).exists(): raise ValueError("Ausente.")
                if Cita.objects.filter(empleado=emp, estado__in=['P','C'], fecha_hora_inicio__lt=fin, fecha_hora_fin__gt=ini).exists(): raise ValueError("Ocupado.")
                c = Cita.objects.create(peluqueria=p, empleado=emp, cliente_nombre=request.POST.get('nombre_cliente'), cliente_telefono=request.POST.get('telefono_cliente'), fecha_hora_inicio=ini, fecha_hora_fin=fin, precio_total=sum([s.precio for s in servs]), estado='P', metodo_pago=request.POST.get('metodo_pago','SITIO'), tipo_cobro=request.POST.get('tipo_cobro','TOTAL'), es_domicilio=request.POST.get('es_domicilio')=='on', direccion_domicilio=request.POST.get('direccion_domicilio'))
                c.servicios.set(servs)
                return c
            
            cita = BookingManager.ejecutar_reserva_segura(emp_id, _crear)
            if cita.metodo_pago == 'BOLD': return redirect('procesar_pago_bold', cita_id=cita.id)
            elif cita.metodo_pago == 'NEQUI': cita.enviar_notificacion_telegram(); return render(request, 'salon/pago_nequi.html', {'cita': cita, 'peluqueria': p})
            else: 
                cita.estado = 'C'; cita.save(); cita.enviar_notificacion_telegram()
                return render(request, 'salon/confirmacion.html', {'cita': cita})
        except Exception as e: return render(request, 'salon/agendar.html', {'peluqueria': p, 'servicios': p.servicios.all(), 'empleados': p.empleados.filter(activo=True), 'error_mensaje': str(e)})
    return render(request, 'salon/agendar.html', {'peluqueria': p, 'servicios': p.servicios.all(), 'empleados': p.empleados.filter(activo=True)})

def confirmacion_cita(request, slug_peluqueria, cita_id): return render(request, 'salon/confirmacion.html', {'cita': get_object_or_404(Cita, id=cita_id)})

def procesar_pago_bold(request, cita_id):
    c = get_object_or_404(Cita, id=cita_id)
    k = c.empleado.bold_secret_key if (c.empleado.es_independiente and c.empleado.bold_secret_key) else c.peluqueria.bold_secret_key
    if not k: return render(request, 'salon/confirmacion.html', {'cita': c, 'mensaje': 'Sin configuración Bold.'})
    try:
        m = int(c.precio_total * (c.peluqueria.porcentaje_abono/100)) if c.tipo_cobro == 'ABONO' else c.precio_total
        r = requests.post("https://integrations.api.bold.co/online/link/v1", json={"name": f"Cita #{c.id}", "description": "Servicio", "amount": m, "currency": "COP", "sku": f"CITA-{c.id}", "redirection_url": request.build_absolute_uri(reverse('retorno_bold'))+f"?cita_id={c.id}"}, headers={"Authorization": f"x-api-key {k}", "Content-Type": "application/json"})
        return redirect(r.json()["payload"]["url"]) if r.status_code==201 else render(request, 'salon/confirmacion.html', {'cita': c, 'mensaje': 'Error Bold.'})
    except: return render(request, 'salon/confirmacion.html', {'cita': c, 'mensaje': 'Conexión Bold falló.'})

def retorno_bold(request):
    c = get_object_or_404(Cita, id=request.GET.get('cita_id'))
    if request.GET.get('payment_status') == 'APPROVED':
        c.estado='C'; c.abono_pagado = int(c.precio_total * (c.peluqueria.porcentaje_abono/100)) if c.tipo_cobro=='ABONO' else c.precio_total; c.save()
        c.enviar_notificacion_telegram()
        return render(request, 'salon/confirmacion.html', {'cita': c, 'mensaje': 'Pago Exitoso'})
    return render(request, 'salon/confirmacion.html', {'cita': c, 'mensaje': 'Pago Rechazado', 'error': True})

def api_obtener_horarios(request):
    try: return JsonResponse({'horas': obtener_bloques_disponibles(Empleado.objects.get(id=request.GET.get('empleado_id')), datetime.strptime(request.GET.get('fecha'), '%Y-%m-%d').date(), timedelta(minutes=30))})
    except: return JsonResponse({'horas': []})
