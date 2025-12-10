# UBICACIÓN: salon/utils/booking_lock.py
from django.db import transaction
from django.core.exceptions import ValidationError
from salon.models import Empleado

class BookingManager:
    """
    🛡️ EL GUARDIA DEL SISTEMA
    Clase utilitaria para manejar reservas de forma atómica y segura
    utilizando bloqueo de filas a nivel de base de datos (Row Locking).
    Evita que dos personas reserven el mismo hueco al mismo tiempo.
    """

    @staticmethod
    def ejecutar_reserva_segura(empleado_id, funcion_creacion_cita, *args, **kwargs):
        """
        Ejecuta una función de creación de cita dentro de un bloqueo estricto.
        
        :param empleado_id: ID del empleado que se va a reservar.
        :param funcion_creacion_cita: La función que crea la cita (debe recibir el objeto empleado como primer arg).
        :return: El resultado de la función de creación.
        """
        try:
            with transaction.atomic():
                # PASO CRÍTICO: Bloqueamos la fila del Empleado (select_for_update).
                # El sistema "congela" este empleado para esta transacción hasta que termine.
                # Cualquier otra petición tendrá que esperar en la fila (el "Guardia" los detiene).
                empleado = Empleado.objects.select_for_update().get(id=empleado_id)
                
                # Verificamos que el empleado siga activo tras el bloqueo
                if not empleado.activo:
                    raise ValidationError("El empleado no está activo o disponible.")

                # Ejecutamos la lógica de negocio (verificar fechas, crear cita, etc.)
                # Pasamos el empleado bloqueado a la función para asegurar que se use esa instancia segura
                resultado = funcion_creacion_cita(empleado, *args, **kwargs)
                
                return resultado

        except Empleado.DoesNotExist:
            raise ValidationError("El empleado especificado no existe.")
        except Exception as e:
            # Re-lanzamos la excepción para que la vista o la API la manejen y muestren el error
            raise e
