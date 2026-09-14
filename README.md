# CryptoVision

CryptoVision is a Flask data analytics and crypto intelligence workspace for uploading arbitrary CSV, Excel, and JSON datasets, cleaning them safely, building Plotly visualizations, and running time-aware forecasts.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

The app connects directly to the MySQL database named `cryptovision`. phpMyAdmin is only used to create or manage that database. Copy `.env.example` to `.env`, set `DB_PASSWORD` and a private `SECRET_KEY`, then create the database using `schema.sql` or phpMyAdmin. Never commit `.env` or real credentials.

## Deploy with Render and Aiven

1. Create an Aiven for MySQL service and a database named `cryptovision`.
2. Export the existing `cryptovision` database from phpMyAdmin, then import the dump into Aiven.
3. Download Aiven's CA certificate. Keep it outside Git locally; in Render upload it as the secret file `ca.pem`.
4. In Render, create a Web Service from this GitHub repository.
5. Use `pip install -r requirements.txt` as the build command and `gunicorn --bind 0.0.0.0:$PORT run:app` as the start command.
6. Add these Render environment variables from Aiven's Connection information: `SECRET_KEY`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and `DB_SSL_CA=/etc/secrets/ca.pem`.

MySQL Workbench uses the same Aiven host, port, database, username, and password. On the SSL tab, select Aiven's downloaded CA certificate and require SSL. Do not put these values in GitHub.
