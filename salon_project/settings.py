import os
from pathlib import Path
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-tu-clave-secreta-aqui')

# ------------------------------------------------------------------------------
# 🔑 CLAVE DE API (INDISPENSABLE)
# NO BORRES ESTO. Tu archivo api.py la necesita para funcionar.
# ------------------------------------------------------------------------------
API_SECRET_KEY = os.environ.get('API_SECRET_KEY', 'mi-clave-super-secreta-cambiame')

# SECURITY WARNING: don't run with debug turned on in production!
# --- DEBUG activado temporalmente para ver errores ---
# Cuando esté todo estable, cámbialo a: 'RENDER' not in os.environ
DEBUG = True 

# ------------------------------------------------------------------------------
# 🚑 CORRECCIÓN DE EMERGENCIA (ALLOWED_HOSTS)
# Lo dejamos en ['*'] para que no te bloquee, sin importar si entras
# por localhost, 127.0.0.1 o una IP de red.
# ------------------------------------------------------------------------------
ALLOWED_HOSTS = ['*'] 


# Application definition

INSTALLED_APPS = [
    'jazzmin', # <--- IMPORTANTE: Jazzmin debe ir PRIMERO, antes de admin
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'salon', 
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'salon.middleware.PeluqueriaMiddleware', # <--- CRÍTICO: Middleware de Multi-tenancy agregado
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'salon_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'salon', 'templates')], # Aseguramos que busque en la carpeta correcta
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            # --- PARCHE PARA JAZZMIN (DJANGO 5.1) ---
            # Esto carga automáticamente el filtro 'length_is' en todas las plantillas
            # para solucionar el error al añadir usuarios o ver listas.
            'builtins': [
                'salon.templatetags.jazzmin_patch',
            ],
        },
    },
]

WSGI_APPLICATION = 'salon_project.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600
    )
}

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'es-co' # Configurado para Colombia/Latam

TIME_ZONE = 'America/Bogota'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# --- CORRECCIÓN 2: WhiteNoise Permisivo ---
# Usamos CompressedStaticFilesStorage en lugar de ManifestStaticFilesStorage
# Esto evita que el sitio se caiga si falta un archivo referenciado en el CSS.
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# 🎨 CONFIGURACIÓN VISUAL (JAZZMIN)
# ==============================================================================

JAZZMIN_SETTINGS = {
    # Título de la pestaña del navegador
    "site_title": "Admin Peluquería",
    
    # Título en la pantalla de login
    "site_header": "Gestión de Citas",
    
    # Título en la barra superior (Brand)
    "site_brand": "Mi Peluquería",
    
    # === AQUÍ ESTÁ EL ARREGLO PARA TU CSS PERSONALIZADO ===
    "custom_css": "css/admin_custom.css",
    # =======================================================
    
    # Logo (pon tu logo en static/img/logo.png o usa una URL externa temporalmente)
    # "site_logo": "img/logo.png",
    
    # Mensaje de bienvenida en el login
    "welcome_sign": "Bienvenido al Panel de Gestión",
    
    # Copyright al pie de página
    "copyright": "CitasPeluqueria App",
    
    # Modelo para buscar globalmente (Ctrl+K)
    "search_model": ["salon.Cita", "salon.Peluqueria"],

    # --- CAMBIO 1: Botones en la barra superior ---
    "topmenu_links": [
        {"name": "Ir al Sitio Web", "url": "inicio", "permissions": ["auth.view_user"]},
        {"name": "Ver Dashboard", "url": "dashboard_dueño", "permissions": ["auth.view_user"]},
        # Este botón llevará al empleado directo a su configuración
        {"name": "📅 Mi Horario y Almuerzo", "url": "mi_horario", "new_window": False},
    ],

    # --- CAMBIO 2: Botón en el menú lateral ---
    # Esto agrega el enlace en el menú de la izquierda, debajo de las apps
    "custom_links": {
        "salon": [{
            "name": "Gestionar Mi Horario", 
            "url": "mi_horario", 
            "icon": "fas fa-clock",
            # Esto asegura que aparezca para usuarios logueados con permiso
            "permissions": ["salon.view_horarioempleado"] 
        }]
    },

    # Iconos para los modelos (busca en fontawesome.com/v5/search)
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "salon.Peluqueria": "fas fa-store",
        "salon.Servicio": "fas fa-cut",
        "salon.Empleado": "fas fa-user-tie",
        "salon.Cita": "fas fa-calendar-check",
        "salon.HorarioSemanal": "fas fa-clock",
        "salon.Ausencia": "fas fa-plane-departure", # Icono de avión para vacaciones
        "salon.PerfilUsuario": "fas fa-id-card",
        "salon.SolicitudSaaS": "fas fa-envelope-open-text",
    },
    
    # Orden del menú lateral
    "order_with_respect_to": ["salon.Cita", "salon.Peluqueria", "salon.Empleado", "salon.Servicio"],

    # Estilo de la interfaz
    "show_ui_builder": True, 
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-pink", 
    "accent": "accent-pink",
    "navbar": "navbar-pink navbar-dark",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-light-pink", 
    "sidebar_nav_small_text": False,
    "theme": "pulse", 
    "dark_mode_theme": "darkly", 
    "button_classes": {
        "primary": "btn-outline-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}
