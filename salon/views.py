from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta

from .models import Tenant, Professional, Service, Product, Appointment, ExternalPayment, Absence
from .forms import ConfigNegocioForm, AbsenceForm

# --- Vistas Públicas ---

def landing_saas_view(request):
    """Página de inicio / Landing Page"""
    # Lógica simple de geolocalización o listado
    ciudades = Tenant.objects.values_list('ciudad', flat=True).distinct()
    peluquerias = Tenant.objects.all()
    
    return render(request, 'salon/index.html', {
        'ciudades': ciudades,
        'peluquerias': peluquerias
    })

def booking_page(request, slug):
    """Vista pública para que el cliente reserve"""
    tenant = get_object_or_404(Tenant, subdomain=slug)
    servicios = tenant.services.all()
    profesionales = tenant.professionals.all()

    if request.method == 'POST':
        servicio_id = request.POST.get('servicio')
        profesional_id = request.POST.get('profesional')
        fecha = request.POST.get('fecha')
        hora = request.POST.get('hora')
        
        # Datos del cliente
        nombre = request.POST.get('nombre_cliente')
        telefono = request.POST.get('telefono_cliente')
        email = request.POST.get('email_cliente')

        try:
            # Construir fecha hora completa
            fecha_hora_str = f"{fecha} {hora}"
            fecha_hora = datetime.strptime(fecha_hora_str, "%Y-%m-%d %H:%M")
            
            servicio_obj = Service.objects.get(id=servicio_id)
            profesional_obj = Professional.objects.get(id=profesional_id)

            # Crear la cita
            cita = Appointment.objects.create(
                tenant=tenant,
                servicio=servicio_obj,
                empleado=profesional_obj,
                fecha_hora_inicio=fecha_hora,
                cliente_nombre=nombre,
                cliente_telefono=telefono,
                cliente_email=email,
                precio_total=servicio_obj.precio,
                estado='confirmada' # O pendiente según tu lógica
            )
            messages.success(request, "¡Cita reservada con éxito!")
            return redirect('confirmacion_reserva', cita_id=cita.id)

        except Exception as e:
            messages.error(request, f"Error al reservar: {str(e)}")
            return redirect('agendar_cita', slug=slug)

    return render(request, 'salon/agendar.html', {
        'tenant': tenant,
        'servicios': servicios,
        'profesionales': profesionales
    })

def confirmation_view(request, cita_id):
    """Vista de confirmación post-reserva"""
    cita = get_object_or_404(Appointment, id=cita_id)
    return render(request, 'salon/confirmacion.html', {
        'cita': cita,
        'mensaje': 'Reserva Exitosa'
    })

# --- Panel de Gestión (Privado) ---

@login_required
def dashboard(request):
    """Panel principal del dueño"""
    # Verificar si tiene un Tenant asociado
    try:
        tenant = request.user.tenants.first()
    except:
        tenant = None

    if not tenant:
        return redirect('crear_negocio')

    # Datos para el dashboard
    citas_hoy = Appointment.objects.filter(
        tenant=tenant, 
        fecha_hora_inicio__date=timezone.now().date()
    ).order_by('fecha_hora_inicio')
    
    context = {
        'tenant': tenant,
        'appointments': citas_hoy,
        'total_sales': 0, # Implementar lógica de ventas si es necesario
    }
    return render(request, 'salon/dashboard.html', context)

@login_required
def create_tenant_view(request):
    """Vista para crear el negocio por primera vez"""
    if request.method == 'POST':
        form = ConfigNegocioForm(request.POST)
        if form.is_valid():
            tenant = form.save(commit=False)
            tenant.user = request.user
            tenant.save()
            messages.success(request, "¡Negocio creado correctamente!")
            return redirect('panel_negocio')
    else:
        form = ConfigNegocioForm()
    
    return render(request, 'salon/create_tenant.html', {'form': form})

@login_required
def create_professional_view(request):
    """Crear un nuevo empleado/profesional"""
    try:
        tenant = request.user.tenants.first()
    except:
        return redirect('inicio')

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            # Opcional: Crear usuario de Django para el empleado
            user_pro = User.objects.create_user(username=email, email=email, password=password)
            
            Professional.objects.create(
                tenant=tenant,
                nombre=nombre,
                email=email,
                user=user_pro
            )
            messages.success(request, "Profesional creado correctamente.")
            return redirect('panel_negocio')
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

    return render(request, 'salon/crear_empleado.html')

# --- Gestión de Agenda y Ausencias ---

@login_required
def client_agenda(request):
    """Vista de agenda para el profesional/dueño"""
    # Si es dueño, ve todo. Si es empleado, ve lo suyo.
    # Por simplicidad asumimos acceso de dueño:
    tenant = request.user.tenants.first()
    citas = Appointment.objects.filter(tenant=tenant).order_by('-fecha_hora_inicio')
    
    return render(request, 'salon/mi_agenda.html', {'citas': citas})

@login_required
def manage_absences(request):
    """Gestionar bloqueos de horario"""
    # Identificar profesional asociado al usuario actual
    try:
        profesional = Professional.objects.get(user=request.user)
    except Professional.DoesNotExist:
        # Si es el dueño, quizás quiera gestionar sus propias ausencias o elegir un pro
        # Simplificación: Redirigir si no es profesional
        messages.error(request, "Debes tener un perfil profesional para gestionar ausencias.")
        return redirect('panel_negocio')

    if request.method == 'POST':
        form = AbsenceForm(request.POST)
        if form.is_valid():
            ausencia = form.save(commit=False)
            ausencia.professional = profesional
            ausencia.save()
            messages.success(request, "Ausencia registrada.")
            return redirect('mis_ausencias')
    else:
        form = AbsenceForm()

    ausencias = Absence.objects.filter(professional=profesional, fecha_inicio__gte=timezone.now())
    
    return render(request, 'salon/ausencias.html', {
        'form': form,
        'ausencias': ausencias
    })

@login_required
def delete_absence(request, absence_id):
    ausencia = get_object_or_404(Absence, id=absence_id)
    # Validar permisos (solo el propio profesional o el dueño)
    if ausencia.professional.user == request.user or request.user.tenants.exists():
        ausencia.delete()
        messages.success(request, "Ausencia eliminada.")
    return redirect('mis_ausencias')

# --- Vistas Placeholder (para evitar errores de importación) ---

@login_required
def settings_view(request):
    return render(request, 'negocio/configuracion.html')

@login_required
def inventory_view(request):
    return render(request, 'salon/dashboard.html') # Placeholder

def pay_external(request, pro_id):
    return render(request, 'salon/pago_bold.html') # Placeholder

def invite_external(request):
    return render(request, 'salon/registro_empleado.html') # Placeholder
