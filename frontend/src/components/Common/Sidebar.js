import React from 'react';
import { Drawer, List, ListItemButton, ListItemIcon, ListItemText, Toolbar, Divider, useTheme, useMediaQuery } from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SettingsIcon from '@mui/icons-material/Settings';
import UploadIcon from '@mui/icons-material/Upload';
import CameraAltIcon from '@mui/icons-material/CameraAlt';
import ArticleIcon from '@mui/icons-material/Article';

const drawerWidth = 240;

function Sidebar({ activeView, onNavigate, mobileOpen, onDrawerToggle, isMobile }) {
  const items = [
    { key: 'dashboard', label: 'Dashboard', icon: <DashboardIcon /> },
    { key: 'cameras', label: 'Cameras', icon: <CameraAltIcon /> },
    { key: 'uploads', label: 'Upload History', icon: <UploadIcon /> },
    { key: 'logs', label: 'Logs', icon: <ArticleIcon /> },
    { key: 'settings', label: 'Settings', icon: <SettingsIcon /> },
  ];

  const drawerContent = (
    <>
      <Toolbar />
      <Divider />
      <List>
        {items.map((item) => (
          <ListItemButton 
            key={item.key} 
            selected={activeView === item.key} 
            onClick={() => {
              onNavigate(item.key);
              if (isMobile) {
                onDrawerToggle();
              }
            }}
          >
            <ListItemIcon>{item.icon}</ListItemIcon>
            <ListItemText primary={item.label} />
          </ListItemButton>
        ))}
      </List>
    </>
  );

  return (
    <>
      {isMobile ? (
        // Mobile: Temporary drawer (hamburger menu)
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={onDrawerToggle}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile
          }}
          sx={{
            [`& .MuiDrawer-paper`]: { 
              width: drawerWidth, 
              boxSizing: 'border-box' 
            },
            zIndex: (theme) => theme.zIndex.drawer + 2,
          }}
        >
          {drawerContent}
        </Drawer>
      ) : (
        // Desktop: Permanent drawer
        <Drawer 
          variant="permanent" 
          sx={{ 
            width: drawerWidth, 
            flexShrink: 0, 
            [`& .MuiDrawer-paper`]: { 
              width: drawerWidth, 
              boxSizing: 'border-box' 
            } 
          }}
        >
          {drawerContent}
        </Drawer>
      )}
    </>
  );
}

export default Sidebar;