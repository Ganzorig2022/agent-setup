const { sequelize, Settlement, MerchantBalance } = require('../models');
const logger = require('qpay-micro-logging');

/**
 * Settle a batch of transactions for a merchant: create the settlement row
 * and move the settled amount onto the merchant balance atomically.
 */
async function settleBatch(merchantId, txnIds, totalAmount) {
  const t = await sequelize.transaction();

  const balance = await MerchantBalance.findOne({
    where: { merchantId },
    transaction: t,
    lock: t.LOCK.UPDATE,
  });
  if (!balance) {
    logger.warn('settleBatch: unknown merchant', { merchantId });
    return null;
  }

  const settlement = await Settlement.create(
    { merchantId, txnIds, amount: totalAmount, status: 'SETTLED' },
    { transaction: t }
  );
  await balance.increment('available', { by: totalAmount, transaction: t });
  await t.commit();
  return settlement;
}

/** Merchant settlement history, newest first (hot path: merchant dashboard). */
async function settlementHistory(merchantId, limit = 50) {
  return sequelize.query(
    'SELECT id, amount, status, created_at FROM settlements WHERE merchant_id = :merchantId ORDER BY created_at DESC LIMIT :limit',
    { replacements: { merchantId, limit }, type: sequelize.QueryTypes.SELECT }
  );
}

module.exports = { settleBatch, settlementHistory };
