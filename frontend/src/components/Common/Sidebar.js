import React from 'react';
import { Drawer, List, ListItemButton, ListItemIcon, ListItemText, Toolbar, Divider } from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SettingsIcon from '@mui/icons-material/Settings';
import UploadIcon from '@mui/icons-material/Upload';
import CameraAltIcon from '@mui/icons-material/CameraAlt';
import ArticleIcon from '@mui/icons-material/Article';

const drawerWidth = 240;

function Sidebar({ activeView, onNavigate }) {
  const items = [
    { key: 'dashboard', label: 'Dashboard', icon: <DashboardIcon /> },
    { key: 'cameras', label: 'Cameras', icon: <CameraAltIcon /> },
    { key: 'uploads', label: 'Upload History', icon: <UploadIcon /> },
    { key: 'logs', label: 'Logs', icon: <ArticleIcon /> },
    { key: 'settings', label: 'Settings', icon: <SettingsIcon /> },
  ];

  return (
    <Drawer variant="permanent" sx={{ width: drawerWidth, flexShrink: 0, [`& .MuiDrawer-paper`]: { width: drawerWidth, boxSizing: 'border-box' } }}>
      <Toolbar />
      <Divider />
      <List>
        {items.map((item) => (
          <ListItemButton key={item.key} selected={activeView === item.key} onClick={() => onNavigate(item.key)}>
            <ListItemIcon>{item.icon}</ListItemIcon>
            <ListItemText primary={item.label} />
          </ListItemButton>
        ))}
      </List>
    </Drawer>
  );
}

export default Sidebar;
