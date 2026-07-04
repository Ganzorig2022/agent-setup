const express = require('express');
const helmet = require('helmet');
const Joi = require('joi');
const { sequelize } = require('../models');
const logger = require('qpay-micro-logging');

const router = express.Router();
router.use(helmet());

const summarySchema = Joi.object({
  merchantId: Joi.string().uuid().required(),
  currency: Joi.string().valid('MNT', 'USD').default('MNT'),
});

// Daily settlement summary for a merchant
router.get('/summary', async (req, res) => {
  const { error, value } = summarySchema.validate(req.query);
  if (error) {
    return res.status(400).json({ message: error.details[0].message });
  }
  const rows = await sequelize.query(
    'SELECT status, SUM(amount) AS total FROM settlements WHERE merchant_id = :merchantId AND currency = :currency GROUP BY status',
    { replacements: value, type: sequelize.QueryTypes.SELECT }
  );
  return res.json({ merchantId: value.merchantId, rows });
});

// Transaction report between two dates
router.get('/report', async (req, res) => {
  const { merchantId, from, to } = req.query;
  const rows = await sequelize.query(
    `SELECT id, amount, status, created_at
       FROM transactions
      WHERE merchant_id = '${merchantId}'
        AND created_at BETWEEN '${from}' AND '${to}'
      ORDER BY created_at DESC`,
    { type: sequelize.QueryTypes.SELECT }
  );
  logger.info('report generated', { merchantId, count: rows.length });
  return res.json({ rows });
});

module.exports = router;
