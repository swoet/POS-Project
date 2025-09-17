import React, { useRef, useEffect, useState } from 'react';

function BarcodeScanner({ onScan, onClose }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [scanning, setScanning] = useState(false);
  const [manualInput, setManualInput] = useState('');

  useEffect(() => {
    startCamera();
    return () => {
      stopCamera();
    };
  }, []);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
        setScanning(true);
        // In a real implementation, you'd use a barcode scanning library
        // For now, we'll simulate scanning
      }
    } catch (error) {
      console.error('Error accessing camera:', error);
      alert('Camera access denied or not available');
    }
  };

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject;
      const tracks = stream.getTracks();
      tracks.forEach(track => track.stop());
    }
    setScanning(false);
  };

  const handleManualScan = () => {
    if (manualInput.trim()) {
      onScan(manualInput.trim());
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleManualScan();
    }
  };

  return (
    <div className="barcode-scanner">
      <div className="scanner-header">
        <h3>Barcode Scanner</h3>
        <button onClick={onClose} className="close-scanner">×</button>
      </div>

      <div className="scanner-content">
        <div className="camera-container">
          <video ref={videoRef} className="camera-feed" />
          <canvas ref={canvasRef} style={{ display: 'none' }} />
          {scanning && <div className="scanner-overlay">Scanning...</div>}
        </div>

        <div className="manual-input">
          <p>Or enter barcode manually:</p>
          <input
            type="text"
            value={manualInput}
            onChange={(e) => setManualInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Enter barcode..."
            className="barcode-input"
          />
          <button onClick={handleManualScan} className="manual-scan-btn">
            Scan
          </button>
        </div>
      </div>

      <div className="scanner-actions">
        <button onClick={stopCamera} disabled={!scanning}>
          Stop Camera
        </button>
        <button onClick={startCamera} disabled={scanning}>
          Start Camera
        </button>
      </div>
    </div>
  );
}

export default BarcodeScanner;