const { app, BrowserWindow, ipcMain } = require('electron')
const path = require('path')
const isDev = process.env.NODE_ENV === 'development'

function createWindow(){
  const win = new BrowserWindow({
    width: 1200, height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      enableRemoteModule: true
    },
    icon: path.join(__dirname, 'assets/icon.png'), // Add icon if available
    show: false
  })

  if (isDev) {
    win.loadURL('http://localhost:3000')
    win.webContents.openDevTools()
  } else {
    win.loadFile(path.join(__dirname, 'build/index.html'))
  }

  win.once('ready-to-show', () => {
    win.show()
  })
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow()
  }
})

// IPC handlers for additional functionality
ipcMain.handle('print-receipt', async (event, receiptData) => {
  // Handle thermal printer integration
  console.log('Printing receipt:', receiptData)
  // Implement printer logic here
})

ipcMain.handle('scan-barcode', async (event) => {
  // Handle barcode scanner integration
  console.log('Scanning barcode...')
  // Implement scanner logic here
})
