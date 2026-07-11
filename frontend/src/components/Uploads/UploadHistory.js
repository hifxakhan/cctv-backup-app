import React, { useEffect, useState } from 'react';
import { Card, CardContent, Table, TableBody, TableCell, TableHead, TableRow, Typography, CircularProgress, TextField } from '@mui/material';
import { getUploads } from '../../services/api';

function UploadHistory() {
  const [uploads, setUploads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const response = await getUploads({ limit: 50 });
        setUploads(response.data);
      } catch (error) {
        console.error('Failed to load uploads:', error);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const filtered = uploads.filter((item) => item.file_name.toLowerCase().includes(search.toLowerCase()));

  return (
    <Card>
      <CardContent>
        <Typography variant="h5" sx={{ mb: 2 }}>Upload History</Typography>
        <TextField label="Search files" value={search} onChange={(event) => setSearch(event.target.value)} sx={{ mb: 2 }} fullWidth />
        {loading ? <CircularProgress /> : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>File</TableCell>
                <TableCell>Size</TableCell>
                <TableCell>Uploaded</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filtered.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>{item.file_name}</TableCell>
                  <TableCell>{item.file_size}</TableCell>
                  <TableCell>{item.upload_date}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

export default UploadHistory;