import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import ProductCatalog from './components/ProductCatalog';
import Cart from './components/Cart';
import Checkout from './components/Checkout';
import Receipt from './components/Receipt';
import Settings from './components/Settings';
import Login from './components/Login';
import './App.css';

const { ipcRenderer } = window.require('electron');

function App() {
  const [cart, setCart] = useState([]);
  const [products, setProducts] = useState([]);
  const [user, setUser] = useState(null);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    // Load local data
    loadLocalData();
    // Check online status
    window.addEventListener('online', () => setIsOnline(true));
    window.addEventListener('offline', () => setIsOnline(false));
    // Load settings
    const settings = JSON.parse(localStorage.getItem('pos_settings') || '{}');
    setDarkMode(settings.darkMode || false);
  }, []);

  const loadLocalData = () => {
    // Load products from local storage or fetch from backend
    const localProducts = JSON.parse(localStorage.getItem('products') || '[]');
    setProducts(localProducts);
    // Load cart
    const localCart = JSON.parse(localStorage.getItem('cart') || '[]');
    setCart(localCart);
  };

  const addToCart = (product, quantity = 1) => {
    setCart(prevCart => {
      const existing = prevCart.find(item => item.id === product.id);
      if (existing) {
        return prevCart.map(item =>
          item.id === product.id
            ? { ...item, quantity: item.quantity + quantity }
            : item
        );
      }
      return [...prevCart, { ...product, quantity }];
    });
  };

  const removeFromCart = (productId) => {
    setCart(prevCart => prevCart.filter(item => item.id !== productId));
  };

  const updateQuantity = (productId, quantity) => {
    if (quantity <= 0) {
      removeFromCart(productId);
      return;
    }
    setCart(prevCart =>
      prevCart.map(item =>
        item.id === productId ? { ...item, quantity } : item
      )
    );
  };

  const clearCart = () => {
    setCart([]);
  };

  const syncData = async () => {
    if (!isOnline) return;
    try {
      // Sync products
      const response = await fetch('http://localhost:8000/products');
      const serverProducts = await response.json();
      setProducts(serverProducts);
      localStorage.setItem('products', JSON.stringify(serverProducts));
    } catch (error) {
      console.error('Sync failed:', error);
    }
  };

  const saveSaleLocally = (sale) => {
    const localSales = JSON.parse(localStorage.getItem('local_sales') || '[]');
    localSales.push(sale);
    localStorage.setItem('local_sales', JSON.stringify(localSales));
  };

  const syncSales = async () => {
    if (!isOnline) return;
    const localSales = JSON.parse(localStorage.getItem('local_sales') || '[]');
    if (localSales.length === 0) return;

    try {
      const response = await fetch('http://localhost:8000/sales/bulk_sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(localSales)
      });
      if (response.ok) {
        localStorage.setItem('local_sales', JSON.stringify([]));
      }
    } catch (error) {
      console.error('Sales sync failed:', error);
    }
  };

  useEffect(() => {
    localStorage.setItem('cart', JSON.stringify(cart));
  }, [cart]);

  useEffect(() => {
    if (isOnline) {
      syncData();
      syncSales();
    }
  }, [isOnline]);

  if (!user) {
    return <Login onLogin={setUser} />;
  }

  return (
    <Router>
      <div className={`app ${darkMode ? 'dark' : ''}`}>
        <header className="header">
          <h1>POS System</h1>
          <div className="header-controls">
            <span className={`status ${isOnline ? 'online' : 'offline'}`}>
              {isOnline ? 'Online' : 'Offline'}
            </span>
            <button onClick={() => setDarkMode(!darkMode)}>
              {darkMode ? 'Light' : 'Dark'} Mode
            </button>
            <Settings />
          </div>
        </header>
        <main className="main">
          <Routes>
            <Route path="/" element={
              <div className="pos-layout">
                <ProductCatalog
                  products={products}
                  onAddToCart={addToCart}
                  isOnline={isOnline}
                />
                <Cart
                  cart={cart}
                  onUpdateQuantity={updateQuantity}
                  onRemove={removeFromCart}
                  onClear={clearCart}
                />
              </div>
            } />
            <Route path="/checkout" element={
              <Checkout
                cart={cart}
                onCheckout={(sale) => {
                  saveSaleLocally(sale);
                  clearCart();
                }}
                isOnline={isOnline}
              />
            } />
            <Route path="/receipt/:saleId" element={<Receipt />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;