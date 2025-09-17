import React, { useRef } from 'react';
import { useReactToPrint } from 'react-to-print';
import { useNavigate } from 'react-router-dom';

function Receipt({ sale }) {
  const componentRef = useRef();
  const navigate = useNavigate();

  const handlePrint = useReactToPrint({
    content: () => componentRef.current,
  });

  if (!sale) {
    return <div>Loading receipt...</div>;
  }

  const items = JSON.parse(sale.items_json || '[]');

  return (
    <div className="receipt-container">
      <div ref={componentRef} className="receipt">
        <div className="receipt-header">
          <h2>POS Receipt</h2>
          <p>Store Name</p>
          <p>Address Line 1</p>
          <p>Address Line 2</p>
          <p>Phone: (123) 456-7890</p>
        </div>

        <div className="receipt-details">
          <p>Date: {new Date(sale.timestamp).toLocaleDateString()}</p>
          <p>Time: {new Date(sale.timestamp).toLocaleTimeString()}</p>
          <p>Receipt #: {sale.id || 'N/A'}</p>
        </div>

        <div className="receipt-items">
          <table>
            <thead>
              <tr>
                <th>Item</th>
                <th>Qty</th>
                <th>Price</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, index) => (
                <tr key={index}>
                  <td>{item.name}</td>
                  <td>{item.quantity}</td>
                  <td>${item.price.toFixed(2)}</td>
                  <td>${(item.price * item.quantity).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="receipt-totals">
          <div className="total-row">
            <span>Subtotal:</span>
            <span>${sale.subtotal.toFixed(2)}</span>
          </div>
          <div className="total-row">
            <span>Tax:</span>
            <span>${sale.tax.toFixed(2)}</span>
          </div>
          <div className="total-row">
            <span>Discount:</span>
            <span>-${sale.discount.toFixed(2)}</span>
          </div>
          <div className="total-row grand-total">
            <span>Total:</span>
            <span>${sale.total.toFixed(2)}</span>
          </div>
        </div>

        <div className="receipt-payment">
          <p>Payment Method: {sale.payment_method}</p>
        </div>

        <div className="receipt-footer">
          <p>Thank you for your business!</p>
          <p>Please come again</p>
        </div>
      </div>

      <div className="receipt-actions">
        <button onClick={handlePrint} className="print-btn">
          Print Receipt
        </button>
        <button onClick={() => navigate('/')} className="new-sale-btn">
          New Sale
        </button>
      </div>
    </div>
  );
}

export default Receipt;