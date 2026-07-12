import React, { useState } from 'react';
import { Box, CssBaseline, Toolbar, useMediaQuery, useTheme } from '@mui/material';
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
  const [mobileOpen, setMobileOpen] = useState(false);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

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
      <Navbar onMenuClick={handleDrawerToggle} />
      <Sidebar 
        activeView={view} 
        onNavigate={setView} 
        mobileOpen={mobileOpen}
        onDrawerToggle={handleDrawerToggle}
        isMobile={isMobile}
      />
      <Box 
        component="main" 
        sx={{ 
          flexGrow: 1, 
          p: { xs: 1, sm: 2, md: 3 },
          width: { xs: '100%', sm: `calc(100% - 240px)` },
          minHeight: '100vh'
        }}
      >
        <Toolbar />
        {renderView()}
      </Box>
    </Box>
  );
}

export default App;