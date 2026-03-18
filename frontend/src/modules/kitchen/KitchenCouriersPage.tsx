import React, { useMemo, useState } from 'react';
import {
  Box,
  Stack,
  TextField,
  Typography,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Chip,
  CircularProgress,
  Alert,
  Button,
  Box as MuiBox,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchCouriersByKitchen, startShift, Courier } from '../../api/courierApi';
import QRCode from 'react-qr-code';
import dayjs from 'dayjs';
import { useCourierWS } from '../../hooks/useCourierWS';

const DEFAULT_KITCHEN_ID = '11111111-1111-1111-1111-111111111111';

const KitchenCouriersPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [kitchenId, setKitchenId] = useState<string>(DEFAULT_KITCHEN_ID);

  useCourierWS({ kitchenId: kitchenId || undefined });

  const { data, isLoading, error } = useQuery({
    queryKey: ['couriersByKitchen', kitchenId],
    queryFn: () => fetchCouriersByKitchen(kitchenId),
    enabled: !!kitchenId,
  });

  const startShiftMutation = useMutation({
    mutationFn: (courierId: string) => startShift(courierId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['couriersByKitchen', kitchenId] });
      queryClient.invalidateQueries({ queryKey: ['availableCouriers'] });
    },
  });

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3} spacing={2}>
        <Box>
          <Typography variant="h5" gutterBottom>
            Курьеры на кухне
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Все курьеры кухни. Чтобы диспатчер мог назначать заказы автоматически, курьер должен быть в смене — нажмите «Начать смену» для офлайн-курьеров.
          </Typography>
        </Box>
        <TextField
          label="Kitchen ID"
          size="small"
          value={kitchenId}
          onChange={(e) => setKitchenId(e.target.value)}
          sx={{ minWidth: 280 }}
        />
      </Stack>

      {isLoading && (
        <Box display="flex" justifyContent="center" mt={4}>
          <CircularProgress />
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Не удалось загрузить курьеров.
        </Alert>
      )}

      {data && (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Имя</TableCell>
              <TableCell>ID</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>Заказов за смену</TableCell>
              <TableCell>Текущие заказы</TableCell>
              <TableCell>Geo trust</TableCell>
              <TableCell>QR прибытия</TableCell>
              <TableCell align="right">Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.items.map((courier: Courier) => (
              <TableRow key={courier.courier_id}>
                <TableCell>{courier.name}</TableCell>
                <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{courier.courier_id}</TableCell>
                <TableCell>
                  <Chip
                    label={courier.status}
                    size="small"
                    color={courier.status === 'idle' || courier.status === 'returning' ? 'success' : 'default'}
                  />
                </TableCell>
                <TableCell>{courier.orders_delivered_today}</TableCell>
                <TableCell>{courier.current_orders.length}</TableCell>
                <TableCell>
                  <Chip
                    label={courier.geo_trust_score.toFixed(2)}
                    size="small"
                    color={courier.geo_trust_score > 0.7 ? 'success' : courier.geo_trust_score > 0.4 ? 'warning' : 'error'}
                  />
                </TableCell>
                <TableCell>
                  {courier.arrival_qr_token &&
                    courier.arrival_qr_expires_at &&
                    dayjs(courier.arrival_qr_expires_at).isAfter(dayjs()) && (
                      <MuiBox textAlign="center">
                        <Typography variant="caption" display="block">
                          {courier.name}
                        </Typography>
                        <MuiBox sx={{ bgcolor: '#fff', p: 1, display: 'inline-block', mt: 0.5, borderRadius: 1 }}>
                          <QRCode value={courier.arrival_qr_token} size={72} />
                        </MuiBox>
                      </MuiBox>
                    )}
                </TableCell>
                <TableCell align="right">
                  {courier.status === 'offline' && (
                    <Button
                      variant="contained"
                      size="small"
                      onClick={() => startShiftMutation.mutate(courier.courier_id)}
                      disabled={startShiftMutation.isPending}
                    >
                      Начать смену
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Box>
  );
};

export default KitchenCouriersPage;
