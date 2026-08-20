const Queue = require('bull');
const logger = require('qpay-micro-logging');
const db = require('qpay-sequelize-postgres');
const { literal } = require('sequelize');
const { NoWalletError } = require('../errors');
const { INVOICE_SMS_STATUS } = require('../constants/invoice');
const { calculateBulkSmsPrice } = require('../services/smsPriceCalculator');
const { buildInvoiceSmsMessage } = require('../utils/invoiceSms');

const smsQueue = new Queue('invoice-sms', process.env.REDIS_URL);

/**
 * Send the SMS batch for an invoice package.
 *
 * Bull is configured with `attempts: 3, backoff: { type: 'exponential' }`.
 */
smsQueue.process(async (job) => {
  const { package_id, merchant_id, merchant_name } = job.data;

  const invoices = await db.findAll(db.Invoice, {
    where: { package_id, sms_status: INVOICE_SMS_STATUS.PENDING },
  });

  let success_count = 0;
  for (const invoice of invoices) {
    const message = buildInvoiceSmsMessage({
      merchantName: merchant_name,
      template: invoice.dataValues.msg_text,
      item: invoice.dataValues,
    });

    await sendSms(invoice.dataValues.phone, message.text);
    await db.update(
      db.Invoice,
      { sms_status: INVOICE_SMS_STATUS.SENT },
      { where: { id: invoice.dataValues.id } }
    );
    success_count += 1;
  }

  return { package_id, merchant_id, merchant_name, success_count };
});

// Wallet deduction runs in the queue's `completed` handler, outside the job
// transaction, because the SMS must be committed as sent before we charge.
smsQueue.on('completed', async (job, result) => {
  const { package_id, merchant_id, merchant_name, success_count } = result;

  try {
    if (success_count > 0) {
      const invoice_list = await db.findAll(db.Invoice, {
        where: { package_id, sms_status: INVOICE_SMS_STATUS.SENT },
      });

      const prepared = invoice_list.map((item) => {
        const built = buildInvoiceSmsMessage({
          merchantName: merchant_name,
          template: item.dataValues.msg_text,
          item: item.dataValues,
        });

        return {
          phone: item.dataValues.phone,
          segmentCount: built.segmentCount || 1,
        };
      });

      // calculateBulkSmsPrice multiplies the per-operator tariff by each
      // message's segment count and returns the total as a string.
      const total_price = await calculateBulkSmsPrice(prepared);

      const wallet = await db.findOne(db.Wallet, {
        where: { merchant_id },
      });

      const new_balance = Number(wallet.dataValues.balance) - Number(total_price);

      await db.update(
        db.Wallet,
        { balance: String(new_balance) },
        { where: { id: wallet.dataValues.id } }
      );

      logger.info(`charged merchant ${merchant_id}: ${total_price}`);
    }
  } catch (walletError) {
    logger.error('wallet deduction failed', walletError);
  }
});

/**
 * Credit a merchant wallet from a bank deposit callback.
 *
 * `wallet_deposit` has a unique index on `provider_txn_id`
 * (migrations/20260714-add-deposit-provider-txn-unique.sql), so a redelivered
 * callback hits the constraint and returns the original receipt instead of
 * crediting twice.
 */
async function recordDeposit({ merchant_id, amount, currency, provider_txn_id }) {
  try {
    return await db.transaction(async (t) => {
      const deposit = await db.create(
        db.WalletDeposit,
        { merchant_id, amount, currency, provider_txn_id },
        { transaction: t }
      );

      const [credited] = await db.update(
        db.Wallet,
        { balance: literal('balance + :amount') },
        {
          where: { merchant_id, currency },
          replacements: { amount },
          transaction: t,
        }
      );

      // 0 rows means no wallet exists for this (merchant, currency) — throw so
      // the deposit row rolls back with it rather than recording an uncredited
      // deposit that the unique index would then replay as "successful".
      if (credited === 0) {
        throw new NoWalletError(merchant_id, currency);
      }

      return deposit;
    });
  } catch (e) {
    if (e.name === 'SequelizeUniqueConstraintError') {
      // The transaction above has already rolled back, so this read runs
      // outside it — reusing the aborted transaction would itself throw.
      return db.findOne(db.WalletDeposit, { where: { provider_txn_id } });
    }
    throw e;
  }
}

async function sendSms(phone, text) {
  return smsQueue.client.publish('sms:outbound', JSON.stringify({ phone, text }));
}

module.exports = { smsQueue, recordDeposit };
