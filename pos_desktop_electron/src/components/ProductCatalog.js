import React, { useState, useEffect } from 'react';
import BarcodeScanner from './BarcodeScanner';

function ProductCatalog({ products, onAddToCart, isOnline }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [categories, setCategories] = useState([]);
  const [showScanner, setShowScanner] = useState(false);

  useEffect(() => {
    if (isOnline) {
      fetchCategories();
    }
  }, [isOnline]);

  const fetchCategories = async () => {
    try {
      const response = await fetch('http://localhost:8000/categories');
      const data = await response.json();
      setCategories(data);
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    }
  };

  const filteredProducts = products.filter(product => {
    const matchesSearch = product.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         (product.barcode && product.barcode.includes(searchTerm));
    const matchesCategory = !selectedCategory || product.category_id === parseInt(selectedCategory);
    return matchesSearch && matchesCategory;
  });

  const handleBarcodeScan = (barcode) => {
    const product = products.find(p => p.barcode === barcode);
    if (product) {
      onAddToCart(product);
    } else {
      alert('Product not found');
    }
    setShowScanner(false);
  };

  return (
    <div className="product-catalog">
      <div className="catalog-header">
        <h2>Product Catalog</h2>
        <div className="search-controls">
          <input
            type="text"
            placeholder="Search products..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="category-select"
          >
            <option value="">All Categories</option>
            {categories.map(category => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
          <button
            onClick={() => setShowScanner(!showScanner)}
            className="scan-button"
          >
            📷 Scan Barcode
          </button>
        </div>
      </div>

      {showScanner && (
        <BarcodeScanner onScan={handleBarcodeScan} onClose={() => setShowScanner(false)} />
      )}

      <div className="products-grid">
        {filteredProducts.map(product => (
          <div key={product.id} className="product-card">
            <h3>{product.name}</h3>
            <p className="product-price">${product.price.toFixed(2)}</p>
            <p className="product-stock">Stock: {product.stock_quantity}</p>
            {product.barcode && <p className="product-barcode">Barcode: {product.barcode}</p>}
            <button
              onClick={() => onAddToCart(product)}
              disabled={product.stock_quantity <= 0}
              className="add-to-cart-btn"
            >
              Add to Cart
            </button>
          </div>
        ))}
      </div>

      {filteredProducts.length === 0 && (
        <div className="no-products">
          <p>No products found matching your search.</p>
        </div>
      )}
    </div>
  );
}

export default ProductCatalog;