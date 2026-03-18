import React, { useState } from 'react';
import {
  Box,
  Button,
  Paper,
  Stack,
  TextField,
  Typography,
  Alert,
  CircularProgress,
  InputAdornment,
} from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { createOrder } from '../../api/orderApi';

const DEFAULT_KITCHEN_ID = '11111111-1111-1111-1111-111111111111';

function toISOLocal(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const KitchenCreateOrderPage: React.FC = () => {
  const navigate = useNavigate();
  const [kitchenId, setKitchenId] = useState(DEFAULT_KITCHEN_ID);
  const [lat, setLat] = useState('55.7558');
  const [lon, setLon] = useState('37.6173');
  const [promisedAt, setPromisedAt] = useState(() => toISOLocal(new Date(Date.now() + 60 * 60 * 1000)));
  const [prepMinutes, setPrepMinutes] = useState<string>('30');

  const createMutation = useMutation({
    mutationFn: () =>
      createOrder({
        kitchen_id: kitchenId,
        customer_location: { lat: parseFloat(lat), lon: parseFloat(lon) },
        promised_delivery_time: new Date(promisedAt).toISOString(),
        preparation_time_estimate_minutes: prepMinutes ? parseInt(prepMinutes, 10) : undefined,
      }),
    onSuccess: () => {
      navigate('/kitchen/orders');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!lat || !lon || !promisedAt) return;
    const latNum = parseFloat(lat);
    const lonNum = parseFloat(lon);
    if (Number.isNaN(latNum) || Number.isNaN(lonNum)) return;
    createMutation.mutate();
  };

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Создать заказ
      </Typography>
      <Typography variant="body2" color="text.secondary" mb={2}>
        Укажите кухню, адрес доставки и желаемое время доставки.
      </Typography>

      <Paper sx={{ p: 3, maxWidth: 520 }}>
        <form onSubmit={handleSubmit}>
          <Stack spacing={2.5}>
            <TextField
              label="Kitchen ID"
              size="small"
              fullWidth
              value={kitchenId}
              onChange={(e) => setKitchenId(e.target.value)}
              required
            />
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                label="Широта"
                size="small"
                type="number"
                inputProps={{ step: 0.0001, min: -90, max: 90 }}
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                InputProps={{ endAdornment: <InputAdornment position="end">lat</InputAdornment> }}
                required
              />
              <TextField
                label="Долгота"
                size="small"
                type="number"
                inputProps={{ step: 0.0001, min: -180, max: 180 }}
                value={lon}
                onChange={(e) => setLon(e.target.value)}
                InputProps={{ endAdornment: <InputAdornment position="end">lon</InputAdornment> }}
                required
              />
            </Stack>
            <TextField
              label="Желаемое время доставки"
              size="small"
              type="datetime-local"
              fullWidth
              value={promisedAt}
              onChange={(e) => setPromisedAt(e.target.value)}
              InputLabelProps={{ shrink: true }}
              required
            />
            <TextField
              label="Время приготовления (мин)"
              size="small"
              type="number"
              inputProps={{ min: 0, max: 120 }}
              value={prepMinutes}
              onChange={(e) => setPrepMinutes(e.target.value)}
              placeholder="опционально"
            />
            {createMutation.isError && (
              <Alert severity="error">{(createMutation.error as Error).message}</Alert>
            )}
            <Stack direction="row" spacing={2} justifyContent="flex-start">
              <Button
                type="submit"
                variant="contained"
                disabled={createMutation.isLoading}
              >
                {createMutation.isLoading ? <CircularProgress size={24} /> : 'Создать заказ'}
              </Button>
              <Button variant="outlined" onClick={() => navigate('/kitchen/orders')}>
                Отмена
              </Button>
            </Stack>
          </Stack>
        </form>
      </Paper>
    </Box>
  );
};

export default KitchenCreateOrderPage;
