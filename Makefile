.PHONY: test

DATABASE_URL ?= sqlite+aiosqlite:////$(CURDIR)/test.db
PYTEST_ARGS ?=

test:
	@DATABASE_URL="$(DATABASE_URL)" python -m pytest -q $(PYTEST_ARGS)



.PHONY: pr
pr:
	@if [ -z "$(CLASS)" ] || [ -z "$(TITLE)" ]; then \
	  echo "Usage: make pr CLASS=A-PATCH TITLE='...' [STAGE=infra]"; \
	  exit 2; \
	fi
	@STAGE=$${STAGE:-infra}; \
	./scripts/pr_create.sh "$(CLASS)" "$(TITLE)" "$$STAGE"
