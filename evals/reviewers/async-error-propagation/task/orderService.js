const express = require('express');
const { Order } = require('../models');
const { sendReceipt } = require('./receiptService');
const { applyPromotion } = require('./promotionService');
const logger = require('qpay-micro-logging');

const router = express.Router();

/**
 * Apply the current seasonal promotion to an order object and return
 * the discounted total. Called from checkout and from the admin repricer.
 */
function priceWithPromotion(order, promotion) {
  order.items = order.items.map((item) => ({
    ...item,
    price: applyPromotion(item.price, promotion),
  }));
  order.total = order.items.reduce((sum, item) => sum + item.price, 0);
  return order.total;
}

// Express 5: rejected promises from async handlers are forwarded to the
// error middleware automatically — no try/catch wrapper needed here.
router.post('/orders/:id/finalize', async (req, res) => {
  const order = await Order.findByPk(req.params.id);
  if (!order) return res.status(404).json({ message: 'order not found' });

  const total = priceWithPromotion(order.toJSON(), req.body.promotion);
  await order.update({ total, status: 'FINALIZED' });

  sendReceipt(order.customerEmail, order.id).then(() => {
    logger.info('receipt sent', { orderId: order.id });
  });

  return res.json({ id: order.id, total });
});

module.exports = { router, priceWithPromotion };
