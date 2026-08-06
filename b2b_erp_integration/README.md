# Hyperpure Integration

## Overview

This module integrates Odoo Purchase Orders with Hyperpure.

## Features

- OTP Authentication
- Outlet Registration
- Product Mapping
- Purchase Order Sync
- Order Status Webhook
- API Logging

## Installation

1. Install module
2. Configure API credentials
3. Authenticate using OTP
4. Map Hyperpure Products
5. Create PO

## Folder Structure

models/
controllers/
wizard/
views/

## API Flow

Odoo PO
      ↓
Validate Vendor
      ↓
Build JSON
      ↓
Call Hyperpure API
      ↓
Receive Response
      ↓
Store Order Log
      ↓
Webhook Updates Status

## Author

Bhargav