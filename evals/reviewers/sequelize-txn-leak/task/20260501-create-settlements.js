'use strict';

/** Migration: settlements table. merchant_id is queried on every dashboard load. */
module.exports = {
  async up(queryInterface, Sequelize) {
    await queryInterface.createTable('settlements', {
      id: { type: Sequelize.UUID, defaultValue: Sequelize.UUIDV4, primaryKey: true },
      merchant_id: {
        type: Sequelize.UUID,
        allowNull: false,
        references: { model: 'merchants', key: 'id' },
      },
      txn_ids: { type: Sequelize.ARRAY(Sequelize.UUID), allowNull: false },
      amount: { type: Sequelize.DECIMAL(18, 2), allowNull: false },
      status: { type: Sequelize.STRING(16), allowNull: false, defaultValue: 'PENDING' },
      created_at: { type: Sequelize.DATE, allowNull: false, defaultValue: Sequelize.NOW },
      updated_at: { type: Sequelize.DATE, allowNull: false, defaultValue: Sequelize.NOW },
    });
  },

  async down(queryInterface) {
    await queryInterface.dropTable('settlements');
  },
};
