# Project Conventions

## Database Migrations

Always use [golang-migrate/migrate](https://github.com/golang-migrate/migrate) to create new migrations:

```bash
migrate create -ext sql -dir migrations -seq <migration_name>
```

This creates properly formatted migration files with sequential numbering.
