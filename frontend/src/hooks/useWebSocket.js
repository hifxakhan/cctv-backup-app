import { useEffect, useState } from 'react';
import { io } from 'socket.io-client';

export const useWebSocket = () => {
  const [socket, setSocket] = useState(null);
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState('connecting');

  useEffect(() => {
    let isMounted = true;
    const client = io(process.env.REACT_APP_API_URL || 'https://cctv-backup.onrender.com', {
      transports: ['polling'],
      upgrade: false,
      rememberUpgrade: false,
      reconnection: true,
      reconnectionAttempts: 8,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 3000,
      timeout: 8000,
      autoConnect: true,
    });

    client.on('connect', () => {
      if (!isMounted) return;
      setSocket(client);
      setStatus('connected');
    });

    client.on('disconnect', () => {
      if (!isMounted) return;
      setStatus('disconnected');
    });

    client.on('connect_error', () => {
      if (!isMounted) return;
      setStatus('error');
    });

    client.on('sync_update', (payload) => {
      if (!isMounted) return;
      setEvents((previous) => [...previous, payload]);
    });

    return () => {
      isMounted = false;
      client.removeAllListeners();
      client.disconnect();
    };
  }, []);

  return { socket, events, status };
};
