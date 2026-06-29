---
name: new-route
description: Add a new API route to a QPay backend service — Express 5, Joi validation, service layer, error handling. Use when adding a new endpoint to any qpay-* service.
---

# New Route — QPay Backend

## File Locations

```
src/apis/<domain>/index.js      # router — add the route here
src/services/<domain>.js        # business logic — add the handler here
src/models/<Model>.js           # only touch if new DB operations needed
```

If the domain folder doesn't exist yet, create `src/apis/<domain>/index.js` and register it in `src/core/`.

## Step 1: Define the Joi Schema First

Validation lives at the route entry — before any service call.

```js
const Joi = require('joi')

// Define schema at the top of the route file
const createInvoiceSchema = Joi.object({
  amount:      Joi.number().positive().required(),
  currency:    Joi.string().valid('MNT', 'USD').required(),
  description: Joi.string().max(255).optional(),
  merchantId:  Joi.string().uuid().required(),
})
```

**Joi rules for QPay routes:**
- Always `.required()` unless the field is truly optional
- Use `.valid()` for enums — never accept arbitrary strings for typed fields
- Use `.uuid()` for ID fields
- Use `.max()` on all string fields — no unbounded inputs
- Use `.strip()` on the overall schema to drop unknown fields: `schema.options({ stripUnknown: true })`

## Step 2: Write the Route Handler

```js
const express = require('express')
const router = express.Router()
const Joi = require('joi')
const invoiceService = require('../../services/invoice.service')

const createInvoiceSchema = Joi.object({ /* ... */ }).options({ stripUnknown: true })

// POST /api/v1/invoices
router.post('/', async (req, res) => {
  const { error, value } = createInvoiceSchema.validate(req.body)
  if (error) {
    return res.status(400).json({ message: error.details[0].message })
  }

  const result = await invoiceService.createInvoice(value)
  return res.status(201).json(result)
})

module.exports = router
```

**Express 5 note:** async errors throw automatically to the error handler — no need for try/catch around `await` calls. The global error middleware in `src/core/` catches them.

## Step 3: Add Business Logic to the Service

```js
// src/services/invoice.service.js

const { Invoice } = require('../models')

async function createInvoice(data) {
  // data is already validated — trust it here
  const invoice = await Invoice.create(data)
  return invoice.toJSON()
}

module.exports = { createInvoice }
```

Keep services free of HTTP concepts (no `req`, `res`, status codes). Services return data or throw errors — routes handle the HTTP layer.

## Step 4: Register the Router

Check `src/core/` or `src/index.js` for where routers are mounted.

```js
// Typical pattern in src/core/routes.js or src/index.js
const invoiceRouter = require('../apis/invoice')
app.use('/api/v1/invoices', invoiceRouter)
```

## Step 5: Validate the Full Flow

```bash
# Start the service
babel-node src/index.js

# Test the happy path
curl -X POST http://localhost:3000/api/v1/invoices \
  -H "Content-Type: application/json" \
  -d '{"amount": 1000, "currency": "MNT", "merchantId": "uuid-here", "description": "test"}'

# Test validation rejection — should return 400
curl -X POST http://localhost:3000/api/v1/invoices \
  -H "Content-Type: application/json" \
  -d '{"amount": -1, "currency": "JPY"}'
```

## Checklist Before Done

- [ ] Joi schema validates all inputs with explicit types and constraints
- [ ] Unknown fields stripped (`stripUnknown: true`)
- [ ] Validation error returns 400 with a human-readable message
- [ ] Service contains no HTTP concepts
- [ ] Router registered in the app
- [ ] Happy path and validation rejection tested manually
