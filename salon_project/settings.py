import os
from pathlib import Path
import dj_database_url

# ==========================================
# 1. CONFIGURACIÓN BASE
# ==========================================

# Ruta base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# SEGURIDAD:
# Usa la variable de entorno SECRET_KEY si existe (Render), si no, usa una clave local insegura.
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-clave-temporal-desarrollo-12345')

# DEBUG: 
# En Render (producción) esto debe ser False. 'RENDER' es una variable que Render inyecta automáticamente.
DEBUG = 'RENDER' not in os.environ

# ALLOWED_HOSTS:
# Permite que la app se vea en cualquier dominio (necesario para Render)
ALLOWED_HOSTS = ['*']

# CSRF:
# Necesario para que funcionen los formularios en Render (https)
CSRF_TRUSTED_ORIGINS = ['https://*.onrender.com']


# ==========================================
# 2. APLICACIONES INSTALADAS
# ==========================================

INSTALLED_APPS = [
    'jazzmin',                    # Panel de admin bonito (debe ir antes de admin)
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Librerías de terceros
    'corsheaders',                # Para permitir peticiones API
    'django_multitenant',         # Si usas multitenant (según requirements)

    # TUS APLICACIONES (IMPORTANTE: Solo 'salon' contiene todo)
    'salon', 
]

# ==========================================
# 3. MIDDLEWARE
# ==========================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',     # CRÍTICO: Sirve archivos estáticos en Render
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',          # CORS para API
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Tu middleware personalizado para manejar el "Tenant" o peluquería actual
    'salon.middleware.PeluqueriaMiddleware',
]

ROOT_URLCONF = 'salon_project.urls'

# ==========================================
# 4. PLANTILLAS (TEMPLATES)
# ==========================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'salon', 'templates')], # Apunta a tu carpeta de templates
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Contexto personalizado para obtener la peluquería actual en el HTML
                'salon.context_processors.tenant_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'salon_project.wsgi.application'


# ==========================================
# 5. BASE DE DATOS
# ==========================================

# Configuración automática para Render (PostgreSQL) o local (SQLite)
DATABASES = {
    'default': dj_database_url.config(
        # Si no hay DATABASE_URL (local), usa sqlite
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
# 8. ARCHIVOS ESTÁTICOS (CSS, JS, IMAGES)
# ==========================================

STATIC_URL = '/static/'

# Carpeta donde Django recolectará todos los estáticos al desplegar (Render lo necesita)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Carpeta donde están tus estáticos de desarrollo
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'salon', 'static'),
]

# Motor de almacenamiento optimizado para Render
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# ==========================================
# 9. OTRAS CONFIGURACIONES
# ==========================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Configuración JAZZMIN (Panel Admin)
JAZZMIN_SETTINGS = {
    "site_title": "Administración PASO",
    "site_header": "PASO Admin",
    "welcome_sign": "Bienvenido al Panel de Control",
    "search_model": "salon.Peluqueria",
    "topmenu_links": [
        {"name": "Ver Sitio", "url": "inicio", "permissions": ["auth.view_user"]},
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

# Configuración CORS (Permitir todo por ahora para evitar bloqueos)
CORS_ALLOW_ALL_ORIGINS = True

# API Key interna para comunicación segura (si usas Flet o APIs externas)
API_SECRET_KEY = os.environ.get('API_SECRET_KEY', 'mi-clave-super-secreta-cambiame')
