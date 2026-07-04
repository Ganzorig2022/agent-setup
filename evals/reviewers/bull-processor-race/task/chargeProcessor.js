const Queue = require('bull');
const logger = require('qpay-micro-logging');
const { chargeCustomer } = require('../services/paymentGateway');
const { Charge } = require('../models');

const CHANNELS = ['qpay-wallet', 'card', 'bank-transfer'];

const chargeQueue = new Queue('recurring-charges', process.env.REDIS_URL);

/**
 * Process a recurring charge job. Bull retries this job up to 3 times
 * (attempts: 3, backoff: exponential) when the processor throws.
 */
chargeQueue.process(async (job) => {
  const { subscriptionId, customerId, amount } = job.data;

  // Fan out availability checks across our three fixed channels.
  const available = [];
  for (const channel of CHANNELS) {
    const ok = await chargeQueue.client.sismember(`channels:up`, channel);
    if (ok) available.push(channel);
  }
  if (available.length === 0) {
    throw new Error('no payment channel available');
  }

  const gatewayRef = await chargeCustomer(customerId, amount, available[0]);

  Charge.create({
    subscriptionId,
    customerId,
    amount,
    gatewayRef,
    channel: available[0],
    status: 'CAPTURED',
  }).catch((err) => {
    logger.error('failed to persist charge', { subscriptionId, err: err.message });
  });

  return { gatewayRef };
});

module.exports = chargeQueue;
