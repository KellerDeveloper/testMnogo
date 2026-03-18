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
} from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { createCourier } from '../../api/courierApi';

const DEFAULT_KITCHEN_ID = '11111111-1111-1111-1111-111111111111';

const OfficeCouriersPage: React.FC = () => {
  const [kitchenId, setKitchenId] = useState(DEFAULT_KITCHEN_ID);
  const [name, setName] = useState('');
  const [maxBatchSize, setMaxBatchSize] = useState<string>('3');

  const createMutation = useMutation({
    mutationFn: () =>
      createCourier({
        kitchen_id: kitchenId,
        name: name.trim(),
        max_batch_size: parseInt(maxBatchSize, 10) || 3,
      }),
    onSuccess: () => {
      setName('');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    createMutation.mutate();
  };

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Добавить курьера
      </Typography>
      <Typography variant="body2" color="text.secondary" mb={2}>
        Создайте нового курьера и привяжите его к кухне. После создания курьер появится в разделе Кухня → Курьеры и сможет начать смену.
      </Typography>

      <Paper sx={{ p: 3, maxWidth: 480 }}>
        <form onSubmit={handleSubmit}>
          <Stack spacing={2.5}>
            <TextField
              label="Kitchen ID"
              size="small"
              fullWidth
              value={kitchenId}
              onChange={(e) => setKitchenId(e.target.value)}
              required
              placeholder="UUID кухни"
            />
            <TextField
              label="Имя курьера"
              size="small"
              fullWidth
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="например: Иванов И."
            />
            <TextField
              label="Макс. заказов в батче"
              size="small"
              type="number"
              inputProps={{ min: 1, max: 10 }}
              value={maxBatchSize}
              onChange={(e) => setMaxBatchSize(e.target.value)}
            />
            {createMutation.isError && (
              <Alert severity="error">{(createMutation.error as Error).message}</Alert>
            )}
            {createMutation.isSuccess && (
              <Alert severity="success">
                Курьер создан: {createMutation.data?.name ?? createMutation.data?.courier_id}. Логин для входа: {createMutation.data?.courier_id}. Передайте логин курьеру.
              </Alert>
            )}
            <Button
              type="submit"
              variant="contained"
              disabled={createMutation.isPending || !name.trim()}
            >
              {createMutation.isPending ? <CircularProgress size={24} /> : 'Создать курьера'}
            </Button>
          </Stack>
        </form>
      </Paper>
    </Box>
  );
};

export default OfficeCouriersPage;
