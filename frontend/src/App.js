import React, { useState } from 'react';
import { Box, CssBaseline, Toolbar } from '@mui/material';
import Navbar from './components/Common/Navbar';
import Sidebar from './components/Common/Sidebar';
import Dashboard from './components/Dashboard/Dashboard';
import Settings from './components/Settings/Settings';
import UploadHistory from './components/Uploads/UploadHistory';
import LogViewer from './components/Logs/LogViewer';
import CameraList from './components/Camera/CameraList';
import './App.css';

function App() {
  const [view, setView] = useState('dashboard');

  const renderView = () => {
    switch (view) {
      case 'settings':
        return <Settings />;
      case 'uploads':
        return <UploadHistory />;
      case 'logs':
        return <LogViewer />;
      case 'cameras':
        return <CameraList />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', backgroundColor: '#f5f7fb' }}>
      <CssBaseline />
      <Navbar />
      <Sidebar activeView={view} onNavigate={setView} />
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        {renderView()}
      </Box>
    </Box>
  );
}

export default App;