"""Ports/adapters locais: nenhum provedor externo é obrigatório para iniciar o MVP."""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import hashlib, hmac, json, os, secrets

class AiProvider(Protocol):
    def summarize(self, text: str) -> dict: ...
    def classify(self, text: str, taxonomy: list[str]) -> dict: ...

class StorageProvider(Protocol):
    def put_private(self, key: str, content: bytes, content_type: str) -> dict: ...
    def delete(self, key: str) -> None: ...

class AntivirusProvider(Protocol):
    def scan(self, content: bytes, filename: str) -> dict: ...

class BillingProvider(Protocol):
    def create_checkout(self, customer_id: str, plan: str) -> dict: ...
    def verify_webhook(self, body: bytes, signature: str) -> bool: ...

@dataclass
class LocalPrivateStorage:
    root: Path
    max_bytes: int = 25 * 1024 * 1024
    def put_private(self, key: str, content: bytes, content_type: str) -> dict:
        if len(content) > self.max_bytes: raise ValueError('arquivo excede o limite local')
        clean = ''.join(c for c in key if c.isalnum() or c in '._/-')
        path = self.root / 'quarantine' / clean
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
        return {'key': str(path.relative_to(self.root)), 'sha256': hashlib.sha256(content).hexdigest(), 'private': True, 'content_type': content_type}
    def delete(self, key: str) -> None:
        p = self.root / key; p.unlink(missing_ok=True)

class QuarantineScanner:
    """Allowlist + hash; ClamAV pode ser injetado sem mudar o domínio."""
    allowed = {'.pdf','.png','.jpg','.jpeg','.docx','.xlsx','.csv','.txt'}
    def scan(self, content: bytes, filename: str) -> dict:
        ext = Path(filename).suffix.lower()
        if ext not in self.allowed: return {'status':'rejected','reason':'extension_not_allowed'}
        if b'<script' in content[:1024].lower(): return {'status':'rejected','reason':'suspicious_content'}
        return {'status':'quarantined','sha256':hashlib.sha256(content).hexdigest(),'antivirus':'not_configured'}

class SandboxBilling:
    def create_checkout(self, customer_id: str, plan: str) -> dict:
        return {'mode':'sandbox','checkout_id':'sandbox_'+secrets.token_urlsafe(10),'customer_id':customer_id,'plan':plan,'requires_external_gateway':True}
    def verify_webhook(self, body: bytes, signature: str) -> bool:
        secret=os.getenv('BILLING_WEBHOOK_SECRET','')
        return bool(secret) and hmac.compare_digest(hmac.new(secret.encode(),body,'sha256').hexdigest(),signature)

class DisabledAi:
    def summarize(self, text: str) -> dict: return {'status':'disabled','draft':True,'text':text[:500],'human_review_required':True}
    def classify(self, text: str, taxonomy: list[str]) -> dict: return {'status':'disabled','draft':True,'labels':[],'human_review_required':True}
