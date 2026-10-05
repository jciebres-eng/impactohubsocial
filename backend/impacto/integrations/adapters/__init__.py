"""Adapters registrados. Identidade (OIDC em services/oidc.py), pagamento (services/billing.py) e e-mail (adapters/mail.py)
já tinham abstração própria por provedor e são REFERENCIADOS no catálogo (não reimplementados aqui)."""
from .bi import BiExportAdapter
from .erp import SeniorSapiensAdapter, TotvsAdapter
from .government import GovernmentApiAdapter
from .rest import GenericRestAdapter

ADAPTERS = {a.key: a for a in (GenericRestAdapter, SeniorSapiensAdapter, TotvsAdapter, GovernmentApiAdapter, BiExportAdapter)}
