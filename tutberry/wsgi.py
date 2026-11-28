import os

from django.core.wsgi import get_wsgi_application
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor

from tutberry.tracing import configure_tracing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tutberry.settings')
configure_tracing('tutberry-api')
PsycopgInstrumentor().instrument()
DjangoInstrumentor().instrument(excluded_urls='health,ready,metrics')
application = get_wsgi_application()
