import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

function Checkout({ cart, onCheckout, isOnline }) {
  const navigate = useNavigate();
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [customerPaid, setCustomerPaid] = useState('');
  const [discount, setDiscount] = useState(0);

  const subtotal = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const tax = subtotal * 0.1; // 10% tax
  const discountAmount = (subtotal * discount) / 100;
  const total = subtotal + tax - discountAmount;
  const change = paymentMethod === 'cash' && customerPaid ? parseFloat(customerPaid) - total : 0;

  const handleCheckout = () => {
    const sale = {
      timestamp: new Date().toISOString(),
      items_json: JSON.stringify(cart.map(item => ({
        product_id: item.id,
        name: item.name,
        price: item.price,
        quantity: item.quantity
      }))),
      subtotal,
      tax,
      discount: discountAmount,
      total,
      payment_method: paymentMethod
    };

    onCheckout(sale);
    navigate(`/receipt/${Date.now()}`);
  };

  return (
    <div className="checkout">
      <h2>Checkout</h2>

      <div className="checkout-summary">
        <h3>Order Summary</h3>
        <div className="summary-items">
          {cart.map(item => (
            <div key={item.id} className="summary-item">
              <span>{item.name} x{item.quantity}</span>
              <span>${(item.price * item.quantity).toFixed(2)}</span>
            </div>
          ))}
        </div>

        <div className="summary-totals">
          <div className="summary-row">
            <span>Subtotal:</span>
            <span>${subtotal.toFixed(2)}</span>
          </div>
          <div className="summary-row">
            <span>Tax (10%):</span>
            <span>${tax.toFixed(2)}</span>
          </div>
          <div className="summary-row">
            <span>Discount ({discount}%):</span>
            <span>-${discountAmount.toFixed(2)}</span>
          </div>
          <div className="summary-row total">
            <span>Total:</span>
            <span>${total.toFixed(2)}</span>
          </div>
        </div>
      </div>

      <div className="checkout-form">
        <div className="form-group">
          <label>Discount (%):</label>
          <input
            type="number"
            value={discount}
            onChange={(e) => setDiscount(parseFloat(e.target.value) || 0)}
            min="0"
            max="100"
            step="0.1"
          />
        </div>

        <div className="form-group">
          <label>Payment Method:</label>
          <select
            value={paymentMethod}
            onChange={(e) => setPaymentMethod(e.target.value)}
          >
            <option value="cash">Cash</option>
            <option value="card">Card</option>
            <option value="digital">Digital Wallet</option>
          </select>
        </div>

        {paymentMethod === 'cash' && (
          <div className="form-group">
            <label>Customer Paid:</label>
            <input
              type="number"
              value={customerPaid}
              onChange={(e) => setCustomerPaid(e.target.value)}
              step="0.01"
              placeholder="0.00"
            />
            {customerPaid && (
              <div className="change-amount">
                Change: ${change.toFixed(2)}
              </div>
            )}
          </div>
        )}

        <div className="checkout-actions">
          <button onClick={() => navigate('/')} className="back-btn">
            Back to Cart
          </button>
          <button
            onClick={handleCheckout}
            className="complete-checkout-btn"
            disabled={!isOnline && paymentMethod !== 'cash'}
          >
            Complete Sale
          </button>
        </div>

        {!isOnline && paymentMethod !== 'cash' && (
          <p className="offline-warning">
            Online payment methods require internet connection
          </p>
        )}
      </div>
    </div>
  );
}

export default Checkout;