import React, { useEffect, useState } from 'react';
import { Card, CardContent, Typography, CircularProgress, List, ListItem, ListItemText } from '@mui/material';
import { getCameras } from '../../services/api';

function CameraList() {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadCameras = async () => {
      const response = await getCameras();
      setCameras(response.data.cameras || []);
      setLoading(false);
    };
    loadCameras();
  }, []);

  return (
    <Card>
      <CardContent>
        <Typography variant="h5" sx={{ mb: 2 }}>Connected Cameras</Typography>
        {loading ? <CircularProgress /> : (
          <List>
            {cameras.map((camera) => (
              <ListItem key={camera.id} divider>
                <ListItemText primary={camera.name} secondary={`Status: ${camera.status}`} />
              </ListItem>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
}

export default CameraList;
