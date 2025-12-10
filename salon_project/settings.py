import os
from pathlib import Path
import dj_database_url

# ==========================================
# 1. CONFIGURACIÓN BASE
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-clave-temporal-desarrollo-12345')
DEBUG = 'RENDER' not in os.environ
ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = ['https://*.onrender.com']


# ==========================================
# 2. APLICACIONES INSTALADAS
# ==========================================

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'django_multitenant',
    'salon', 
]

# ==========================================
# 3. MIDDLEWARE
# ==========================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # COMENTAR ESTA LÍNEA TEMPORALMENTE PARA DIAGNÓSTICO
    'salon.middleware.PeluqueriaMiddleware',
]

ROOT_URLCONF = 'salon_project.urls'

# ==========================================
# 4. PLANTILLAS
# ==========================================

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
                'salon.context_processors.tenant_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'salon_project.wsgi.application'

# ==========================================
# 5. BASE DE DATOS
# ==========================================

DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600
    )
}

# ==========================================
# 6. VALIDACIÓN DE PASSWORD
# ==========================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==========================================
# 7. INTERNATIONALIZATION
# ==========================================

LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

# ==========================================
# 8. ESTÁTICOS
# ==========================================

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'salon', 'static'),
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ==========================================
# 9. OTRAS CONFIGURACIONES
# ==========================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- CONFIGURACIÓN JAZZMIN (CORREGIDA) ---
JAZZMIN_SETTINGS = {
    "site_title": "Administración PASO",
    "site_header": "PASO Admin",
    "welcome_sign": "Bienvenido al Panel de Control",
    "search_model": "salon.Peluqueria",
    
    # 1. Menú Superior
    "topmenu_links": [
        {"name": "Ver Sitio", "url": "inicio", "permissions": ["auth.view_user"]},
    ],

    # 2. Sidebar Custom Links (CORREGIDO: 'mi_horario' -> 'mi_agenda')
    "custom_links": {
        "salon": [{
            "name": "📅 Gestionar Horario", 
            "url": "mi_agenda", 
            "icon": "fas fa-clock",
            "permissions": ["auth.view_user"]
        }]
    },

    # 3. User Menu (CORREGIDO: 'mi_horario' -> 'mi_agenda')
    "usermenu_links": [
        {"name": "📅 Mi Horario Visual", "url": "mi_agenda", "new_window": True, "icon": "fas fa-clock"},
    ],

    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "salon.Peluqueria": "fas fa-store",
        "salon.Cita": "fas fa-calendar-check",
        "salon.Empleado": "fas fa-user-tie",
        "salon.Servicio": "fas fa-cut",
    },
}

CORS_ALLOW_ALL_ORIGINS = True
API_SECRET_KEY = os.environ.get('API_SECRET_KEY', 'mi-clave-super-secreta-cambiame')

LOGIN_REDIRECT_URL = 'inicio'
LOGOUT_REDIRECT_URL = 'inicio'
