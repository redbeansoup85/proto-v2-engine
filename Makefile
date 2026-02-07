.PHONY: test
test:
	DATABASE_URL="sqlite+aiosqlite:///$(PWD)/test.db" python -m pytest -q
