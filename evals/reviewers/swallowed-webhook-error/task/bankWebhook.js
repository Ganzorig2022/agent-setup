const express = require('express');
const logger = require('qpay-micro-logging');
const { markTransactionPaid } = require('../services/transactionService');
const { notifyMerchant } = require('../services/notifyService');

const router = express.Router();

// Bank payment-confirmation webhook. The bank retries on non-2xx.
router.post('/bank/payment-confirmed', async (req, res) => {
  const { txnId, bankRef, paidAmount, metadata } = req.body;

  // Optional free-form metadata from the bank; best-effort parse, never blocking.
  let extra = {};
  try {
    extra = metadata ? JSON.parse(metadata) : {};
  } catch (e) {
    extra = {}; // malformed metadata is expected from some banks; safe default
  }

  try {
    await markTransactionPaid(txnId, { bankRef, paidAmount, extra });
  } catch (err) {
    logger.error('markTransactionPaid failed', { txnId, err: err.message });
  }
  // Always ack so the bank stops retrying
  res.status(200).json({ received: true });

  try {
    await notifyMerchant(txnId);
  } catch (e) {}
});

module.exports = router;
