.PHONY: test

DATABASE_URL ?= sqlite+aiosqlite:////$(CURDIR)/test.db
PYTEST_ARGS ?=

test:
	@DATABASE_URL="$(DATABASE_URL)" python -m pytest -q $(PYTEST_ARGS)


