# Rista API Tester

A lightweight local web application for testing the Rista API with JWT authentication.

## Requirements

- Python 3.12+

## Installation

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

If PowerShell execution policy blocks activation:

```powershell
venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and add your credentials:

```
RISTA_API_KEY=your_api_key
RISTA_SECRET_KEY=your_secret_key
```

Do **not** commit `.env` to version control.

## Run

```powershell
python app.py
```

Open http://127.0.0.1:5000

## How JWT Authentication Works

```
API Key + Secret Key
         ↓
      JWT (HS256)
         ↓
  x-api-key + x-api-token
         ↓
     Rista API
```

## Troubleshooting

### 401 Authentication Failed
- Verify `RISTA_API_KEY` is correct
- Verify `RISTA_SECRET_KEY` is correct
- Ensure the JWT has not expired (tokens are short-lived)

### 403 Permission Denied
- Check API permissions for your Rista API key
- Verify the endpoint is enabled for your account

### 404 Not Found
- Verify the endpoint path (e.g. `/branch/list`)
- Confirm your Rista subscription includes the endpoint

### Connection Errors
- Check internet connectivity
- Verify `RISTA_BASE_URL` is correct
