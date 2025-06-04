.PHONY: install test clean

install:
	pip install -r requirements.txt

test:
	pytest

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov 