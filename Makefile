# Atalhos de desenvolvimento. Requer: Python 3.11+, Node 20+, PostgreSQL 16 (ou docker compose), libpq5.
ADMIN_DATABASE_URL ?= postgresql://postgres@127.0.0.1:5432/postgres
.PHONY: db web dev test e2e audit release
db:        ## recria banco de desenvolvimento com papéis e migrations
	ADMIN_DATABASE_URL=$(ADMIN_DATABASE_URL) scripts/dev_reset_db.sh
web:       ## build da SPA/PWA
	cd web && node build.mjs
dev:       ## API + SPA em http://localhost:8080 (exige DATABASE_URL exportada)
	cd backend && IMPACTO_ENV=development ./run_dev.sh
test:      ## suíte completa (Postgres real + HTTP real + navegador)
	cd backend && PASSWORD_SCRYPT_N=16384 RATE_LIMIT_MULTIPLIER=1000 TEST_ADMIN_DATABASE_URL=$(ADMIN_DATABASE_URL) python3 -m unittest discover -s tests -t .
audit:
	cd backend && pip-audit -r requirements.txt && cd ../web && npm audit --omit=dev
release:   ## gera RELEASE_MANIFEST.sha256 e FINAL_FULL_RELEASE.zip
	python3 scripts/make_release.py
