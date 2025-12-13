# UBICACIÓN: salon/management/commands/fix_profiles.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from salon.models import PerfilUsuario

class Command(BaseCommand):
    help = 'Repara usuarios que no tienen perfil y causan Error 500'

    def handle(self, *args, **kwargs):
        self.stdout.write("🚑 Iniciando reparación de perfiles...")
        
        count = 0
        for user in User.objects.all():
            # get_or_create verifica si existe, si no, lo crea.
            perfil, created = PerfilUsuario.objects.get_or_create(user=user)
            
            if created:
                self.stdout.write(self.style.SUCCESS(f"✅ Perfil creado para usuario: {user.username}"))
                count += 1
                
                # Si es superusuario, le damos permisos de dueño automáticamente
                if user.is_superuser:
                    perfil.es_dueño = True
                    perfil.save()
                    self.stdout.write(self.style.WARNING(f"   👑 {user.username} ahora marcado como Dueño"))
            else:
                # Asegurar que el superadmin siempre sea dueño
                if user.is_superuser and not perfil.es_dueño:
                    perfil.es_dueño = True
                    perfil.save()
                    self.stdout.write(self.style.WARNING(f"   👑 Permisos de dueño restaurados para {user.username}"))

        self.stdout.write(self.style.SUCCESS(f"✨ Proceso terminado. {count} perfiles reparados."))
