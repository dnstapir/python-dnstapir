all:

test:
	poetry run pytest --ruff --ruff-format

lint:
	poetry run ruff check .

reformat:
	poetry run ruff check --select I --fix .
	poetry run ruff format .

clean:

realclean: clean
	poetry env remove --all
