# HealSync Backend Migration

This directory is the new backend boundary for the FastAPI service. The legacy `app/` package remains available during migration and is not deleted until the new repository contract has equivalent tests.

## Target runtime

- Python FastAPI exposed through Firebase Functions
- Firebase Auth for identity verification
- Firestore for production persistence
- Firebase Storage for private original documents
- SQLite via Python `sqlite3` for local development and tests

## Migration rule

API routers must depend on repository interfaces, never on MongoDB collection methods. SQLite and Firestore implementations will satisfy the same interfaces. MongoDB is not part of the target architecture.

## Local commands

```powershell
$env:PYTHONPATH = 'src'
python -m healsync_backend.app
```

The old root `app/` remains the compatibility implementation while routes are moved one slice at a time.
