import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Alert,
  Stack,
  TextField,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  SelectChangeEvent,
  List,
  ListItem,
  ListItemText,
  Divider,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchCourier,
  startShift,
  endShift,
  updateCourierStatus,
  updateCourierLocation,
  recordDelivery,
  Courier,
  CourierStatus,
} from '../../api/courierApi';
import { fetchOrder, updateOrderStatus } from '../../api/orderApi';
import { useCourierWS } from '../../hooks/useCourierWS';

const COURIER_ID_STORAGE = 'dispatcher_courier_id';

const CourierOrdersPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [courierId, setCourierIdState] = useState(() => localStorage.getItem(COURIER_ID_STORAGE) ?? '');
  const [locLat, setLocLat] = useState('');
  const [locLon, setLocLon] = useState('');
  const [deliveryMinutes, setDeliveryMinutes] = useState<string>('15');

  useEffect(() => {
    if (courierId) localStorage.setItem(COURIER_ID_STORAGE, courierId);
  }, [courierId]);

  useCourierWS({ courierId: courierId || undefined });

  const { data: courier, isLoading, error } = useQuery({
    queryKey: ['courier', courierId],
    queryFn: () => fetchCourier(courierId),
    enabled: !!courierId,
  });

  const orderIds = courier?.current_orders ?? [];
  const { data: orders, isLoading: ordersLoading } = useQuery({
    queryKey: ['ordersForCourier', orderIds],
    queryFn: async () => {
      const results = await Promise.all(orderIds.map((id) => fetchOrder(id).catch(() => null)));
      return results.filter(Boolean) as Awaited<ReturnType<typeof fetchOrder>>[];
    },
    enabled: orderIds.length > 0,
  });

  const startShiftMutation = useMutation({
    mutationFn: () => startShift(courierId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['courier', courierId] }),
  });
  const endShiftMutation = useMutation({
    mutationFn: () => endShift(courierId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['courier', courierId] }),
  });
  const statusMutation = useMutation({
    mutationFn: (newStatus: CourierStatus) => updateCourierStatus(courierId, newStatus),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['courier', courierId] }),
  });
  const locationMutation = useMutation({
    mutationFn: () => updateCourierLocation(courierId, parseFloat(locLat), parseFloat(locLon)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['courier', courierId] }),
  });
  const pickedUpMutation = useMutation({
    mutationFn: ({ orderId }: { orderId: string }) =>
      updateOrderStatus(orderId, { status: 'picked_up', courier_id: courierId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['courier', courierId] });
      queryClient.invalidateQueries({ queryKey: ['ordersForCourier'] });
    },
  });
  const deliveredMutation = useMutation({
    mutationFn: ({ orderId }: { orderId: string }) =>
      recordDelivery(courierId, orderId, parseInt(deliveryMinutes, 10) || 0),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['courier', courierId] });
      queryClient.invalidateQueries({ queryKey: ['ordersForCourier'] });
    },
  });
  const orderDeliveredMutation = useMutation({
    mutationFn: ({ orderId }: { orderId: string }) =>
      updateOrderStatus(orderId, { status: 'delivered', courier_id: courierId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ordersForCourier'] }),
  });

  const handleStatusChange = (e: SelectChangeEvent) => {
    statusMutation.mutate(e.target.value as CourierStatus);
  };

  if (!courierId) {
    return (
      <Box>
        <Typography variant="h5" gutterBottom>
          Мои заказы
        </Typography>
        <Typography variant="body2" color="text.secondary" mb={2}>
          Введите ваш Courier ID (сохраняется в браузере).
        </Typography>
        <TextField
          label="Courier ID"
          size="small"
          fullWidth
          value={courierId}
          onChange={(e) => setCourierIdState(e.target.value)}
          placeholder="6-значный логин из раздела Кухня → Курьеры или Офис"
          sx={{ maxWidth: 420 }}
        />
      </Box>
    );
  }

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2} flexWrap="wrap" gap={2}>
        <Box>
          <Typography variant="h5" gutterBottom>
            Мои заказы
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Курьер: {courier?.name ?? courierId}
          </Typography>
        </Box>
        <TextField
          label="Courier ID"
          size="small"
          value={courierId}
          onChange={(e) => setCourierIdState(e.target.value)}
          sx={{ width: 320 }}
        />
      </Stack>

      {isLoading && (
        <Box display="flex" justifyContent="center" py={4}>
          <CircularProgress />
        </Box>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Курьер с таким ID не найден. Проверьте ID или создайте курьера в разделе Кухня → Курьеры.
        </Alert>
      )}

      {courier && (
        <Stack spacing={2}>
          <Card variant="outlined">
            <CardContent>
              <Stack direction="row" alignItems="center" flexWrap="wrap" gap={2} mb={2}>
                <Typography variant="subtitle1">{courier.name}</Typography>
                <Chip label={courier.status} size="small" color={courier.status === 'idle' ? 'success' : 'default'} />
                <Typography variant="body2" color="text.secondary">
                  Заказов в смене: {courier.orders_delivered_today} · Сейчас: {courier.current_orders.length}/{courier.max_batch_size}
                </Typography>
              </Stack>
              <Stack direction="row" spacing={2} flexWrap="wrap">
                <Button
                  variant="contained"
                  size="small"
                  onClick={() => startShiftMutation.mutate()}
                  disabled={startShiftMutation.isPending || courier.status !== 'offline'}
                >
                  Начать смену
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => endShiftMutation.mutate()}
                  disabled={endShiftMutation.isPending || courier.current_orders.length > 0}
                >
                  Закончить смену
                </Button>
                <FormControl size="small" sx={{ minWidth: 140 }}>
                  <InputLabel>Статус</InputLabel>
                  <Select
                    label="Статус"
                    value={courier.status}
                    onChange={handleStatusChange}
                    disabled={statusMutation.isPending}
                  >
                    <MenuItem value="idle">idle</MenuItem>
                    <MenuItem value="delivering">delivering</MenuItem>
                    <MenuItem value="returning">returning</MenuItem>
                    <MenuItem value="offline">offline</MenuItem>
                  </Select>
                </FormControl>
              </Stack>
            </CardContent>
          </Card>

          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                Обновить геолокацию
              </Typography>
              <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
                <TextField
                  size="small"
                  label="Широта"
                  type="number"
                  value={locLat}
                  onChange={(e) => setLocLat(e.target.value)}
                  sx={{ width: 120 }}
                />
                <TextField
                  size="small"
                  label="Долгота"
                  type="number"
                  value={locLon}
                  onChange={(e) => setLocLon(e.target.value)}
                  sx={{ width: 120 }}
                />
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => locationMutation.mutate()}
                  disabled={locationMutation.isPending || !locLat || !locLon}
                >
                  Отправить
                </Button>
              </Stack>
            </CardContent>
          </Card>

          <Typography variant="subtitle1" gutterBottom>
            Текущие заказы ({orderIds.length})
          </Typography>
          {ordersLoading && orderIds.length > 0 && <CircularProgress size={24} />}
          {orders && orders.length === 0 && orderIds.length > 0 && (
            <Alert severity="info">Не удалось загрузить детали заказов.</Alert>
          )}
          {orders && orders.length > 0 && (
            <List disablePadding>
              {orders.map((order, i) => (
                <React.Fragment key={order.order_id}>
                  {i > 0 && <Divider />}
                  <ListItem
                    alignItems="flex-start"
                    sx={{ flexWrap: 'wrap', gap: 1 }}
                    secondaryAction={
                      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                        {order.status === 'assigned' && (
                          <Button
                            size="small"
                            variant="contained"
                            onClick={() => pickedUpMutation.mutate({ orderId: order.order_id })}
                            disabled={pickedUpMutation.isPending}
                          >
                            Забрал
                          </Button>
                        )}
                        {order.status === 'picked_up' && (
                          <>
                            <TextField
                              size="small"
                              type="number"
                              label="Мин в пути"
                              value={deliveryMinutes}
                              onChange={(e) => setDeliveryMinutes(e.target.value)}
                              sx={{ width: 90 }}
                              inputProps={{ min: 0, max: 120 }}
                            />
                            <Button
                              size="small"
                              variant="contained"
                              color="success"
                              onClick={() => {
                                deliveredMutation.mutate({ orderId: order.order_id });
                                orderDeliveredMutation.mutate({ orderId: order.order_id });
                              }}
                              disabled={deliveredMutation.isPending || orderDeliveredMutation.isPending}
                            >
                              Доставлен
                            </Button>
                          </>
                        )}
                      </Stack>
                    }
                  >
                    <ListItemText
                      primary={order.order_id}
                      secondary={
                        <>
                          <Chip label={order.status} size="small" sx={{ mr: 1 }} />
                          Дедлайн: {order.promised_delivery_time}
                        </>
                      }
                    />
                  </ListItem>
                </React.Fragment>
              ))}
            </List>
          )}
          {orderIds.length === 0 && courier.current_orders.length === 0 && (
            <Typography variant="body2" color="text.secondary">
              Нет активных заказов. Новые появятся после назначения с кухни или диспатчера.
            </Typography>
          )}
        </Stack>
      )}
    </Box>
  );
};

export default CourierOrdersPage;
