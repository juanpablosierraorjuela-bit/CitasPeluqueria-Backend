# salon/management/commands/auditar_sistema.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from salon.models import Cita, Peluqueria

class Command(BaseCommand):
    help = 'Ejecuta un diagnóstico completo del sistema para encontrar citas superpuestas y errores de datos.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Iniciando auditoría del sistema...'))
        
        errores_encontrados = 0
        citas_corregidas = 0

        # 1. DETECTAR CITAS SUPERPUESTAS (El resultado del Bug de Concurrencia)
        citas_activas = Cita.objects.filter(estado__in=['P', 'C']).order_by('empleado', 'fecha_hora_inicio')
        
        # Iteramos (esto podría optimizarse con Window Functions en PostgreSQL, pero lo hacemos pythonico por compatibilidad)
        for i in range(len(citas_activas) - 1):
            cita_actual = citas_activas[i]
            siguiente_cita = citas_activas[i+1]

            # Verificar si son del mismo empleado
            if cita_actual.empleado_id == siguiente_cita.empleado_id:
                # Verificar superposición: Si la siguiente empieza antes de que termine la actual
                if siguiente_cita.fecha_hora_inicio < cita_actual.fecha_hora_fin:
                    self.stdout.write(self.style.ERROR(
                        f"CONFLICTO DETECTADO: Cita {cita_actual.id} choca con Cita {siguiente_cita.id} "
                        f"para el empleado {cita_actual.empleado.nombre}."
                    ))
                    
                    # Lógica de Auto-Reparación (Opcional: Marcar la más reciente como Anulada por Conflicto)
                    siguiente_cita.estado = 'A' # Anulamos la segunda
                    siguiente_cita.cliente_nombre += " [ANULADA POR CONFLICTO SISTEMA]"
                    siguiente_cita.save()
                    
                    self.stdout.write(self.style.SUCCESS(f" -> Cita {siguiente_cita.id} anulada automáticamente."))
                    errores_encontrados += 1
                    citas_corregidas += 1

        # 2. DETECTAR PELUQUERÍAS SIN CONFIGURACIÓN CRÍTICA
        peluquerias = Peluqueria.objects.all()
        for p in peluquerias:
            if not p.servicios.exists():
                self.stdout.write(self.style.WARNING(f"Alerta: La peluquería '{p.nombre}' no tiene servicios configurados."))
            if not p.empleados.filter(activo=True).exists():
                self.stdout.write(self.style.WARNING(f"Alerta: La peluquería '{p.nombre}' no tiene estilistas activos."))

        # 3. LIMPIEZA DE CITAS PENDIENTES VIEJAS (Basura de intentos fallidos)
        limite_tiempo = timezone.now() - timezone.timedelta(minutes=30)
        citas_basura = Cita.objects.filter(estado='P', creado_en__lt=limite_tiempo, referencia_pago_bold__isnull=True)
        count_basura = citas_basura.count()
        if count_basura > 0:
            citas_basura.delete()
            self.stdout.write(self.style.SUCCESS(f"Limpieza: Se eliminaron {count_basura} citas pendientes abandonadas."))

        self.stdout.write(self.style.SUCCESS('--------------------------------------------------'))
        self.stdout.write(self.style.SUCCESS(f'Auditoría finalizada. Conflictos resueltos: {citas_corregidas}.'))
