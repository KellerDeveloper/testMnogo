import React, { useState } from 'react';
import { Box, Stack, TextField, Typography, Card, CardContent, CircularProgress, Alert } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchCourierStatsSummary } from '../../api/courierApi';

const CourierStatsPage: React.FC = () => {
  const [courierId, setCourierId] = useState<string>('');

  useCourierWS({ courierId: courierId || undefined });

  const { data, isLoading, error } = useQuery({
    queryKey: ['courierStats', courierId],
    queryFn: () => fetchCourierStatsSummary(courierId),
    enabled: !!courierId,
  });

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Статистика смены
      </Typography>
      <Typography variant="body2" color="text.secondary" mb={2}>
        Введите ID курьера, чтобы посмотреть его статистику по смене.
      </Typography>

      <Stack direction="row" spacing={2} mb={3}>
        <TextField
          label="Courier ID"
          size="small"
          fullWidth
          value={courierId}
          onChange={(e) => setCourierId(e.target.value)}
        />
      </Stack>

      {isLoading && (
        <Box display="flex" justifyContent="center" mt={4}>
          <CircularProgress />
        </Box>
      )}

      {error && courierId && (
        <Alert severity="error">Не удалось загрузить статистику для этого курьера.</Alert>
      )}

      {data && (
        <Card sx={{ maxWidth: 420 }}>
          <CardContent>
            <Typography variant="subtitle1" gutterBottom>
              Курьер {data.name ?? data.courier_id}
            </Typography>
            <Typography variant="h4">{data.orders_delivered_today}</Typography>
            <Typography variant="body2" color="text.secondary">
              заказов за смену
            </Typography>
            <Box mt={2}>
              <Typography variant="body2">
                Среднее по кухне: {data.kitchen_avg_orders_today.toFixed(1)}
              </Typography>
              <Typography variant="body2">
                Позиция по заказам: {data.rank_by_orders} из {data.total_couriers_on_kitchen}
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default CourierStatsPage;
