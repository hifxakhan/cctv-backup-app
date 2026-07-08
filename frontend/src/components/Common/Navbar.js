import React from 'react';
import { AppBar, Toolbar, Typography, Box } from '@mui/material';

function Navbar() {
  return (
    <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
      <Toolbar>
        <Typography variant="h6" noWrap component="div">
          CCTV Backup Dashboard
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Typography variant="body2">Secure backup monitoring</Typography>
      </Toolbar>
    </AppBar>
  );
}

export default Navbar;
