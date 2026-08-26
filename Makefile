ENV_FILE ?= .env.development
BOOTSTRAP_RETRIES ?= 30
BOOTSTRAP_RETRY_SLEEP ?= 2
PERF_BASE_URL ?= http://127.0.0.1:8000
PERF_REQUESTS ?= 120
PERF_CONCURRENCY ?= 20
PERF_P95_MS ?= 700
DR_BACKUP_DIR ?= backups
SECURITY_SCAN_STRICT ?= true

.PHONY: run stop lint logs build shell test db-upgrade db-makemigration db-recreate db-reset smoke smoke-ci live-smoke seed seed-sample verify-seed verify-relations cleanup-test-data validate bootstrap-zero documentacion docs-audit gate-go-no-go security-scan perf-smoke dr-backup dr-verify enterprise-gate enterprise-gate-runtime

run:
	docker compose --env-file $(ENV_FILE) up --build -d

stop:
	docker compose --env-file $(ENV_FILE) down

lint:
	poetry run ruff check .
	poetry run mypy -p osiris

logs:
	docker compose logs -f

build:
	docker compose --env-file $(ENV_FILE) build

shell:
	docker compose --env-file $(ENV_FILE) exec osiris-backend bash

test:
	@echo "Aplicando migraciones (alembic upgrade head)..."
	docker compose --env-file $(ENV_FILE) exec osiris-backend bash -lc 'ENVIRONMENT=development DB_URL_ALEMBIC="$$DATABASE_URL" poetry run alembic upgrade head'
	@echo "Limpiando datos de prueba..."
	docker compose --env-file $(ENV_FILE) exec osiris-backend bash -c "ENVIRONMENT=development poetry run python scripts/cleanup_test_data.py"
	@echo "Ejecutando suite de pruebas..."
	docker compose --env-file $(ENV_FILE) exec osiris-backend bash -lc 'cd /app && env -u FEEC_P12_PATH -u FEEC_P12_PASSWORD -u FEEC_XSD_PATH -u FEEC_AMBIENTE -u SRI_MODO_EMISION -u FEEC_TIPO_EMISION -u FEEC_REGIMEN -u DATABASE_URL -u DB_URL_ALEMBIC RUN_LIVE_SMOKE=true PYTHONPATH=/app:/app/src poetry run pytest -v'

db-upgrade:
	docker compose --env-file $(ENV_FILE) exec osiris-backend bash -lc 'DB_URL_ALEMBIC="$$DATABASE_URL" poetry run alembic upgrade head'

db-makemigration:
	docker compose --env-file .env.development exec -e ENVIRONMENT=development osiris-backend bash -lc 'DB_URL_ALEMBIC="$$DATABASE_URL" poetry run alembic revision --autogenerate -m "$(mensaje)"'
	docker compose --env-file .env.development exec osiris-backend bash -lc 'DB_URL_ALEMBIC="$$DATABASE_URL" poetry run alembic upgrade head'

db-recreate:
	docker compose --env-file .env.development exec postgres bash -lc '\
	  set -euo pipefail; \
	  if psql -U "$$POSTGRES_USER" -d postgres -h localhost -tAc "SELECT 1 FROM pg_database WHERE datname='\''$$POSTGRES_DB'\''" | grep -q 1; then \
	    psql -U "$$POSTGRES_USER" -d postgres -h localhost -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='\''$$POSTGRES_DB'\''"; \
	    psql -U "$$POSTGRES_USER" -d postgres -h localhost -c "DROP DATABASE \"$$POSTGRES_DB\""; \
	  else \
	    echo \"DB $$POSTGRES_DB no existe, skip DROP\"; \
	  fi'
	docker compose --env-file .env.development exec postgres bash -lc '\
	  set -euo pipefail; \
	  if ! psql -U "$$POSTGRES_USER" -d postgres -h localhost -tAc "SELECT 1 FROM pg_database WHERE datname='\''$$POSTGRES_DB'\''" | grep -q 1; then \
	    psql -U "$$POSTGRES_USER" -d postgres -h localhost -c "CREATE DATABASE \"$$POSTGRES_DB\""; \
	  else \
	    echo \"DB $$POSTGRES_DB ya existe, skip CREATE\"; \
	  fi'
	docker compose --env-file .env.development exec osiris-backend bash -lc 'set -euo pipefail; DB_URL_ALEMBIC="$$DATABASE_URL" poetry run alembic upgrade head'
	docker compose --env-file .env.development exec postgres bash -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -h localhost -c "\dt"'
	docker compose --env-file .env.development exec postgres bash -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -h localhost -c "select * from alembic_version;"'

db-reset:
	# DROP condicional (si existe) + matar conexiones abiertas
	docker compose --env-file .env.development exec postgres bash -lc '\
	  set -euo pipefail; \
	  if psql -U "$$POSTGRES_USER" -d postgres -h localhost -tAc "SELECT 1 FROM pg_database WHERE datname='\''$$POSTGRES_DB'\''" | grep -q 1; then \
	    echo ">> Terminating backends for $$POSTGRES_DB"; \
	    psql -U "$$POSTGRES_USER" -d postgres -h localhost -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='\''$$POSTGRES_DB'\''"; \
	    echo ">> Dropping database $$POSTGRES_DB"; \
	    psql -U "$$POSTGRES_USER" -d postgres -h localhost -c "DROP DATABASE \"$$POSTGRES_DB\""; \
	  else \
	    echo ">> DB $$POSTGRES_DB no existe, skip DROP"; \
	  fi'

	# CREATE condicional (solo si no existe)
	docker compose --env-file .env.development exec postgres bash -lc '\
	  set -euo pipefail; \
	  if ! psql -U "$$POSTGRES_USER" -d postgres -h localhost -tAc "SELECT 1 FROM pg_database WHERE datname='\''$$POSTGRES_DB'\''" | grep -q 1; then \
	    echo ">> Creating database $$POSTGRES_DB"; \
	    psql -U "$$POSTGRES_USER" -d postgres -h localhost -c "CREATE DATABASE \"$$POSTGRES_DB\""; \
	  else \
	    echo ">> DB $$POSTGRES_DB ya existe, skip CREATE"; \
	  fi'

	# Verificación: la DB está vacía (sin tablas)
	docker compose --env-file .env.development exec postgres bash -lc '\
	  psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -h localhost -c "\dt" || true'

smoke:
	docker compose --env-file $(ENV_FILE) up -d --build
	poetry run pytest -q tests/smoke
	docker compose --env-file $(ENV_FILE) down

smoke-ci:
	# Levanta la pila (si necesitas que corra en CI; quitar --build si ya está en image cache)
	docker compose --env-file $(ENV_FILE) up -d --build
	# Ejecuta solo las pruebas list-only (seguras para CI)
	poetry run pytest -q tests/smoke/test_list_only.py
	docker compose --env-file $(ENV_FILE) down

live-smoke:
	@echo ">> Ejecutando smoke live (requiere servidor HTTP real)..."
	RUN_LIVE_SMOKE=true poetry run pytest -q tests/live_smoke -rs

seed:
	docker compose --env-file $(ENV_FILE) exec osiris-backend bash -c "ENVIRONMENT=development PYTHONPATH=src poetry run python scripts/seed_complete_data.py"

seed-sample:
	docker compose --env-file $(ENV_FILE) exec osiris-backend bash -c "PYTHONPATH=src poetry run python scripts/seed_sample_product.py"

verify-seed:
	docker compose --env-file $(ENV_FILE) exec osiris-backend bash -c "ENVIRONMENT=development PYTHONPATH=src poetry run python scripts/check_seed_data.py"

verify-relations:
	docker compose --env-file $(ENV_FILE) exec osiris-backend bash -c "ENVIRONMENT=development PYTHONPATH=src poetry run python scripts/check_producto_relations.py"

cleanup-test-data:
	docker compose --env-file $(ENV_FILE) exec osiris-backend bash -c "ENVIRONMENT=development PYTHONPATH=src poetry run python scripts/cleanup_test_data.py"

validate:
	poetry run python scripts/validate_setup.py

bootstrap-zero:
	@echo ">> Reiniciando entorno desde cero (containers + volumenes)..."
	docker compose --env-file $(ENV_FILE) down --remove-orphans --volumes
	@echo ">> Levantando contenedores..."
	docker compose --env-file $(ENV_FILE) up --build -d
	@echo ">> Esperando a backend (poetry)..."
	@attempt=1; \
	until docker compose --env-file $(ENV_FILE) exec -T osiris-backend bash -lc 'poetry --version >/dev/null 2>&1'; do \
		if [ $$attempt -ge $(BOOTSTRAP_RETRIES) ]; then \
			echo "ERROR: osiris-backend no estuvo listo tras $(BOOTSTRAP_RETRIES) intentos."; \
			exit 1; \
		fi; \
		echo "Intento $$attempt/$(BOOTSTRAP_RETRIES): backend no listo, reintentando en $(BOOTSTRAP_RETRY_SLEEP)s..."; \
		attempt=$$((attempt + 1)); \
		sleep $(BOOTSTRAP_RETRY_SLEEP); \
	done
	@echo ">> Sincronizando dependencias Python (poetry install --no-root)..."
	@attempt=1; \
	until docker compose --env-file $(ENV_FILE) exec -T osiris-backend bash -lc 'poetry config virtualenvs.create false && poetry install --no-root'; do \
		if [ $$attempt -ge $(BOOTSTRAP_RETRIES) ]; then \
			echo "ERROR: no se pudieron instalar dependencias tras $(BOOTSTRAP_RETRIES) intentos."; \
			exit 1; \
		fi; \
		echo "Intento $$attempt/$(BOOTSTRAP_RETRIES): fallo poetry install, reintentando en $(BOOTSTRAP_RETRY_SLEEP)s..."; \
		attempt=$$((attempt + 1)); \
		sleep $(BOOTSTRAP_RETRY_SLEEP); \
	done
	@echo ">> Esperando a PostgreSQL..."
	@attempt=1; \
	until docker compose --env-file $(ENV_FILE) exec -T postgres bash -lc 'pg_isready -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -h localhost >/dev/null 2>&1'; do \
		if [ $$attempt -ge $(BOOTSTRAP_RETRIES) ]; then \
			echo "ERROR: PostgreSQL no estuvo listo tras $(BOOTSTRAP_RETRIES) intentos."; \
			exit 1; \
		fi; \
		echo "Intento $$attempt/$(BOOTSTRAP_RETRIES): PostgreSQL no listo, reintentando en $(BOOTSTRAP_RETRY_SLEEP)s..."; \
		attempt=$$((attempt + 1)); \
		sleep $(BOOTSTRAP_RETRY_SLEEP); \
	done
	@echo ">> Aplicando migraciones..."
	@attempt=1; \
	until docker compose --env-file $(ENV_FILE) exec -T osiris-backend bash -lc 'ENVIRONMENT=development DB_URL_ALEMBIC="$$DATABASE_URL" poetry run alembic upgrade head'; do \
		if [ $$attempt -ge $(BOOTSTRAP_RETRIES) ]; then \
			echo "ERROR: migraciones fallaron tras $(BOOTSTRAP_RETRIES) intentos."; \
			exit 1; \
		fi; \
		echo "Intento $$attempt/$(BOOTSTRAP_RETRIES): migracion fallida, reintentando en $(BOOTSTRAP_RETRY_SLEEP)s..."; \
		attempt=$$((attempt + 1)); \
		sleep $(BOOTSTRAP_RETRY_SLEEP); \
	done
	@echo ">> Ejecutando seed..."
	@attempt=1; \
	until docker compose --env-file $(ENV_FILE) exec -T osiris-backend bash -lc 'ENVIRONMENT=development PYTHONPATH=/app:/app/src poetry run python scripts/seed_complete_data.py'; do \
		if [ $$attempt -ge $(BOOTSTRAP_RETRIES) ]; then \
			echo "ERROR: seed fallo tras $(BOOTSTRAP_RETRIES) intentos."; \
			exit 1; \
		fi; \
		echo "Intento $$attempt/$(BOOTSTRAP_RETRIES): seed fallido, reintentando en $(BOOTSTRAP_RETRY_SLEEP)s..."; \
		attempt=$$((attempt + 1)); \
		sleep $(BOOTSTRAP_RETRY_SLEEP); \
	done
	@echo ">> Entorno listo."
	@$(MAKE) documentacion
	@echo ">> API y Docs estan corriendo."

documentacion:
	@echo ">> Levantando entorno de documentacion..."
	docker compose --env-file $(ENV_FILE) up -d --force-recreate docs

docs-audit:
	@echo ">> Auditando cobertura docs/docs/api contra src/osiris/modules..."
	poetry run python scripts/audit_docs_api_coverage.py

gate-go-no-go:
	@echo ">> [Gate] Lint tecnico..."
	poetry run ruff check src tests
	@echo ">> [Gate] Suite de pruebas..."
	@set -e; \
	poetry run pytest -q -rs > /tmp/osiris_gate_pytest.log; \
	cat /tmp/osiris_gate_pytest.log; \
	if grep -q "SKIPPED" /tmp/osiris_gate_pytest.log; then \
		echo "ERROR: Gate falló porque se detectaron tests SKIPPED en la suite principal."; \
		exit 1; \
	fi
	@echo ">> [Gate] Build de documentacion..."
	cd docs && npm run build --silent
	@echo ">> [Gate] Resultado: GO (todas las validaciones pasaron)."

security-scan:
	@echo ">> [Security] Preparando herramientas de escaneo..."
	@echo ">> [Security] Normalizando constraints del wheel local fe-ec..."
	poetry run python scripts/patch_feec_wheel_constraints.py --wheel lib/fe_ec-0.1.0-py3-none-any-3.whl
	@echo ">> [Security] Sincronizando lock e instalación de dependencias..."
	poetry lock --no-interaction --regenerate --no-cache
	poetry install --no-interaction --no-root
	@echo ">> [Security] Actualizando pip en el entorno de auditoría..."
	poetry run python -m pip install --quiet --cache-dir /tmp/pip-cache --upgrade pip
	@mkdir -p /tmp/pip-audit-cache
	poetry run python -c "import importlib.util,sys;missing=[m for m in ('bandit','pip_audit') if importlib.util.find_spec(m) is None];sys.exit(0 if not missing else 1)" \
	|| poetry run python -m pip install --quiet --cache-dir /tmp/pip-cache bandit pip-audit
	@echo ">> [Security] Ejecutando Bandit..."
	poetry run bandit -q -r src -x src/osiris/db/alembic
	@echo ">> [Security] Ejecutando pip-audit..."
	@set -e; \
	if ! poetry run pip-audit --cache-dir /tmp/pip-audit-cache; then \
		if [ "$(SECURITY_SCAN_STRICT)" = "true" ]; then \
			echo "ERROR: pip-audit fallo (modo estricto)."; \
			exit 1; \
		fi; \
		echo "WARN: pip-audit no disponible en este entorno (modo no estricto)."; \
	fi
	@echo ">> [Security] Escaneo en verde."

perf-smoke:
	@echo ">> [Perf] Ejecutando smoke de latencia/concurrencia..."
	poetry run python scripts/perf_smoke.py \
		--base-url $(PERF_BASE_URL) \
		--requests $(PERF_REQUESTS) \
		--concurrency $(PERF_CONCURRENCY) \
		--p95-ms-threshold $(PERF_P95_MS)

dr-backup:
	@mkdir -p $(DR_BACKUP_DIR)
	@backup_file="$(DR_BACKUP_DIR)/osiris_backup_$$(date +%Y%m%d_%H%M%S).sql"; \
	echo ">> [DR] Generando backup en $$backup_file ..."; \
	docker compose --env-file $(ENV_FILE) exec -T postgres bash -lc 'PGPASSWORD="$$POSTGRES_PASSWORD" pg_dump -U "$$POSTGRES_USER" -h localhost "$$POSTGRES_DB"' > "$$backup_file"; \
	echo ">> [DR] Backup generado correctamente."

dr-verify:
	@mkdir -p $(DR_BACKUP_DIR)
	@backup_file="$(DR_BACKUP_DIR)/dr_verify_$$(date +%Y%m%d_%H%M%S).sql"; \
	verify_db="osiris_dr_verify"; \
	echo ">> [DR] Exportando backup temporal para verificacion..."; \
	docker compose --env-file $(ENV_FILE) exec -T postgres bash -lc 'PGPASSWORD="$$POSTGRES_PASSWORD" pg_dump -U "$$POSTGRES_USER" -h localhost "$$POSTGRES_DB"' > "$$backup_file"; \
	echo ">> [DR] Restaurando en base de verificacion $$verify_db ..."; \
	docker compose --env-file $(ENV_FILE) exec -T postgres bash -lc 'set -euo pipefail; \
		PGPASSWORD="$$POSTGRES_PASSWORD" psql -U "$$POSTGRES_USER" -h localhost -d postgres -c "DROP DATABASE IF EXISTS \"'$$verify_db'\""; \
		PGPASSWORD="$$POSTGRES_PASSWORD" psql -U "$$POSTGRES_USER" -h localhost -d postgres -c "CREATE DATABASE \"'$$verify_db'\""' ; \
	cat "$$backup_file" | docker compose --env-file $(ENV_FILE) exec -T postgres bash -lc 'PGPASSWORD="$$POSTGRES_PASSWORD" psql -U "$$POSTGRES_USER" -h localhost "'"$$verify_db"'" >/dev/null'; \
	docker compose --env-file $(ENV_FILE) exec -T postgres bash -lc 'PGPASSWORD="$$POSTGRES_PASSWORD" psql -U "$$POSTGRES_USER" -h localhost -d "'"$$verify_db"'" -c "SELECT COUNT(*) AS tablas FROM information_schema.tables WHERE table_schema='\''public'\'';"'; \
	docker compose --env-file $(ENV_FILE) exec -T postgres bash -lc 'PGPASSWORD="$$POSTGRES_PASSWORD" psql -U "$$POSTGRES_USER" -h localhost -d postgres -c "DROP DATABASE IF EXISTS \"'$$verify_db'\""' ; \
	echo ">> [DR] Verificacion backup/restore completada."

enterprise-gate:
	@echo ">> [Enterprise Gate] Gate tecnico base..."
	@$(MAKE) gate-go-no-go
	@echo ">> [Enterprise Gate] Seguridad..."
	@$(MAKE) security-scan
	@echo ">> [Enterprise Gate] Cobertura documental..."
	@$(MAKE) docs-audit
	@echo ">> [Enterprise Gate] Resultado: GO enterprise."

enterprise-gate-runtime:
	@echo ">> [Enterprise Runtime Gate] Validaciones runtime..."
	@$(MAKE) perf-smoke
	@$(MAKE) dr-verify
	@echo ">> [Enterprise Runtime Gate] Resultado: GO runtime."
