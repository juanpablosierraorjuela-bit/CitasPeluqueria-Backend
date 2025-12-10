import os
from pathlib import Path
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-tu-clave-secreta-aqui')

# ------------------------------------------------------------------------------
# 🔑 CLAVE DE API
# ------------------------------------------------------------------------------
API_SECRET_KEY = os.environ.get('API_SECRET_KEY', 'mi-clave-super-secreta-cambiame')

LOGIN_REDIRECT_URL = '/dashboard/'

# Cambiar a False en producción real
DEBUG = 'RENDER' not in os.environ

ALLOWED_HOSTS = ['*']

# ------------------------------------------------------------------------------
# 🚨 CORRECCIÓN CRÍTICA DJANGO 5 (HTTPS)
# ------------------------------------------------------------------------------
# Si usas Render, Railway o un dominio propio con HTTPS, debes agregarlo aquí.
# Ejemplo: 'https://mi-peluqueria.onrender.com'
CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
    'https://*.railway.app',
    'http://127.0.0.1:8000',
    'http://localhost:8000'
]

INSTALLED_APPS = [
    'jazzmin',
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
    'whitenoise.middleware.WhiteNoiseMiddleware', # WhiteNoise debe ir aquí
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'salon.middleware.PeluqueriaMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'salon_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'salon', 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'salon.context_processors.tenant_context', # Tu context processor
            ],
            'builtins': [
                'salon.templatetags.jazzmin_patch',
            ],
        },
    },
]

WSGI_APPLICATION = 'salon_project.wsgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600
    )
}

AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]

LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Configuración robusta para WhiteNoise en producción
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# JAZZMIN SETTINGS
# ==============================================================================
JAZZMIN_SETTINGS = {
    "site_title": "Admin Peluquería",
    "site_header": "Gestión de Citas",
    "site_brand": "Mi Peluquería",
    "custom_css": "css/admin_custom.css",
    "welcome_sign": "Bienvenido al Panel de Gestión",
    "copyright": "CitasPeluqueria App",
    # CORRECCIÓN: Search model debe ser exacto
    "search_model": ["salon.Cita", "salon.Peluqueria"],
    "topmenu_links": [
        {"name": "Ir al Sitio Web", "url": "inicio", "permissions": ["auth.view_user"]},
        {"name": "Ver Dashboard", "url": "dashboard_dueño", "permissions": ["auth.view_user"]},
        {"name": "📅 Mi Horario y Almuerzo", "url": "mi_horario", "new_window": False},
    ],
    "custom_links": {
        "salon": [{
            "name": "Gestionar Mi Horario", 
            "url": "mi_horario", 
            "icon": "fas fa-clock",
            "permissions": ["salon.view_horarioempleado"] 
        }]
    },
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "salon.Peluqueria": "fas fa-store",
        "salon.Servicio": "fas fa-cut",
        "salon.Empleado": "fas fa-user-tie",
        "salon.Cita": "fas fa-calendar-check",
        "salon.Ausencia": "fas fa-plane-departure",
        "salon.PerfilUsuario": "fas fa-id-card",
        "salon.SolicitudSaaS": "fas fa-envelope-open-text",
    },
    "order_with_respect_to": ["salon.Cita", "salon.Peluqueria", "salon.Empleado", "salon.Servicio"],
    "show_ui_builder": False, 
}

JAZZMIN_UI_TWEAKS = {
    "brand_colour": "navbar-pink",
    "accent": "accent-pink",
    "navbar": "navbar-pink navbar-dark",
    "no_navbar_border": False,
    "sidebar": "sidebar-light-pink",
    "theme": "pulse",
}
