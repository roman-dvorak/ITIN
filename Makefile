up:
	docker compose up --build

down:
	docker compose down

migrate:
	docker compose run --rm web python manage.py migrate

makemigrations:
	docker compose run --rm web python manage.py makemigrations

test:
	docker compose run --rm web python manage.py test

createsuperuser:
	docker compose run --rm web python manage.py createsuperuser

load-fixtures:
	docker compose run --rm web python manage.py loaddata inventory/fixtures/demo_data.json
