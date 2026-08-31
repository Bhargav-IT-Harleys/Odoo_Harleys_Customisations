# Architecture

This module follows a layered architecture:

- models: Odoo business objects and data models
- services: orchestration and integration logic
- services/adapters: vendor-specific implementations
- controllers: webhook and health endpoints
- wizard: OTP and manual sync workflows
- views: UI definitions and menus
