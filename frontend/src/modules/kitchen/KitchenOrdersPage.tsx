import React, { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  SelectChangeEvent,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
  Chip,
  CircularProgress,
  Alert,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchOrders, manualAssign, markReadyForDispatch, Order, OrderStatus } from '../../api/orderApi';
import { fetchAvailableCouriers, fetchCouriersByKitchen, Courier } from '../../api/courierApi';
import { useOrderWS } from '../../hooks/useOrderWS';
import { useCourierWS } from '../../hooks/useCourierWS';

const DEFAULT_KITCHEN_ID = '11111111-1111-1111-1111-111111111111';

const KitchenOrdersPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [kitchenId, setKitchenId] = useState<string>(DEFAULT_KITCHEN_ID);
  const [statusFilter, setStatusFilter] = useState<OrderStatus | ''>('');
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [selectedCourier, setSelectedCourier] = useState<Courier | null>(null);
  const [overrideReason, setOverrideReason] = useState<string>('');

  const { connected: ordersWS } = useOrderWS(kitchenId || undefined);
  const { connected: couriersWS } = useCourierWS({ kitchenId: kitchenId || undefined });
  const wsConnected = ordersWS && couriersWS;

  const {
    data: orders,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['orders', kitchenId, statusFilter],
    queryFn: () => fetchOrders({ kitchen_id: kitchenId || undefined, status: statusFilter || undefined }),
  });

  const {
    data: availableCouriers,
    isLoading: couriersLoading,
    error: couriersError,
  } = useQuery({
    queryKey: ['availableCouriers', kitchenId, selectedOrder?.order_id],
    queryFn: () => fetchAvailableCouriers(kitchenId),
    enabled: !!selectedOrder && !!kitchenId,
  });

  const { data: couriersByKitchen } = useQuery({
    queryKey: ['couriersByKitchen', kitchenId],
    queryFn: () => fetchCouriersByKitchen(kitchenId),
    enabled: !!kitchenId,
  });
  const courierIdToName = React.useMemo(() => {
    const m = new Map<string, string>();
    couriersByKitchen?.items?.forEach((c: Courier) => m.set(c.courier_id, c.name));
    return m;
  }, [couriersByKitchen]);

  const assignMutation = useMutation({
    mutationFn: (params: { orderId: string; courierId: string; reason?: string }) =>
      manualAssign(params.orderId, {
        operator_id: 'operator-1',
        courier_id: params.courierId,
        override_reason: params.reason || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      queryClient.invalidateQueries({ queryKey: ['availableCouriers'] });
      setSelectedOrder(null);
      setSelectedCourier(null);
      setOverrideReason('');
    },
  });

  const readyMutation = useMutation({
    mutationFn: (orderId: string) => markReadyForDispatch(orderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
  });

  const handleStatusChange = (event: SelectChangeEvent) => {
    setStatusFilter(event.target.value as OrderStatus | '');
  };

  const handleOpenAssign = (order: Order) => {
    setSelectedOrder(order);
  };

  const handleCloseDialog = () => {
    if (assignMutation.isLoading) return;
    setSelectedOrder(null);
    setSelectedCourier(null);
    setOverrideReason('');
  };

  const handleAssign = () => {
    if (!selectedOrder || !selectedCourier) return;
    assignMutation.mutate({
      orderId: selectedOrder.order_id,
      courierId: selectedCourier.courier_id,
      reason: overrideReason || undefined,
    });
  };

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3} spacing={2}>
        <Box>
          <Typography variant="h5" gutterBottom>
            Очередь заказов
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Для заказов «new» нажмите «Готов к отправке» — диспатчер назначит курьера автоматически (нужен хотя бы один курьер в смене; один курьер может взять несколько заказов в батч). Для «pending» — вручную.
          </Typography>
        </Box>
        <Stack direction="row" spacing={2} flexWrap="wrap">
          <Button component={RouterLink} to="/kitchen/orders/create" variant="contained" size="medium">
            Создать заказ
          </Button>
          <TextField
            label="Kitchen ID"
            size="small"
            value={kitchenId}
            onChange={(e) => setKitchenId(e.target.value)}
            sx={{ minWidth: 280 }}
          />
          <Chip
            size="small"
            label={wsConnected ? 'Онлайн · обновления в реальном времени' : 'Подключение…'}
            color={wsConnected ? 'success' : 'default'}
            variant={wsConnected ? 'filled' : 'outlined'}
            sx={{ alignSelf: 'center' }}
          />
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel id="status-filter-label">Статус</InputLabel>
            <Select
              labelId="status-filter-label"
              label="Статус"
              value={statusFilter}
              onChange={handleStatusChange}
            >
              <MenuItem value="">Все</MenuItem>
              <MenuItem value="new">new</MenuItem>
              <MenuItem value="pending">pending</MenuItem>
              <MenuItem value="assigned">assigned</MenuItem>
              <MenuItem value="picked_up">picked_up</MenuItem>
              <MenuItem value="delivered">delivered</MenuItem>
              <MenuItem value="cancelled">cancelled</MenuItem>
            </Select>
          </FormControl>
        </Stack>
      </Stack>

      {isLoading && (
        <Box display="flex" justifyContent="center" mt={4}>
          <CircularProgress />
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Не удалось загрузить заказы.
        </Alert>
      )}

      {orders && (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>Kitchen</TableCell>
              <TableCell>Дедлайн</TableCell>
              <TableCell>Исполнитель</TableCell>
              <TableCell align="right">Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {orders.items.map((order) => (
              <TableRow key={order.order_id} hover>
                <TableCell>{order.order_id}</TableCell>
                <TableCell>
                  <Chip label={order.status} size="small" />
                </TableCell>
                <TableCell>{order.kitchen_id}</TableCell>
                <TableCell>{order.promised_delivery_time}</TableCell>
                <TableCell>
                  {order.assigned_courier_id ? (
                    <Chip
                      label={courierIdToName.get(order.assigned_courier_id) ?? order.assigned_courier_id}
                      size="small"
                      color={order.assigned_carrier_type === '3pl' ? 'secondary' : 'default'}
                    />
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      Не назначен
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right">
                  {order.status === 'new' && (
                    <Button
                      variant="contained"
                      size="small"
                      onClick={() => readyMutation.mutate(order.order_id)}
                      disabled={readyMutation.isPending}
                    >
                      Готов к отправке
                    </Button>
                  )}
                  {order.status === 'pending' && (
                    <Button variant="outlined" size="small" onClick={() => handleOpenAssign(order)}>
                      Назначить вручную
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={!!selectedOrder} onClose={handleCloseDialog} fullWidth maxWidth="md">
        <DialogTitle>Ручное назначение заказа</DialogTitle>
        <DialogContent dividers>
          {selectedOrder && (
            <Box mb={2}>
              <Typography variant="subtitle1">Заказ {selectedOrder.order_id}</Typography>
              <Typography variant="body2" color="text.secondary">
                Kitchen: {selectedOrder.kitchen_id} · Дедлайн: {selectedOrder.promised_delivery_time}
              </Typography>
            </Box>
          )}
          {couriersLoading && (
            <Box display="flex" justifyContent="center" my={2}>
              <CircularProgress size={24} />
            </Box>
          )}
          {couriersError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              Не удалось загрузить курьеров.
            </Alert>
          )}
          {availableCouriers && (
            <Stack direction="row" spacing={2} alignItems="flex-start">
              <Box flex={2}>
                <Typography variant="subtitle2" gutterBottom>
                  Доступные курьеры
                </Typography>
                {availableCouriers.items.length === 0 && (
                  <Alert severity="info" sx={{ mb: 2 }}>
                    Сейчас нет курьеров в смене (статус idle). Запустите смену в разделе <strong>Кухня → Курьеры</strong>: нажмите «Начать смену» у нужного курьера — тогда он появится здесь и диспатчер сможет назначать заказы автоматически.
                  </Alert>
                )}
                {availableCouriers.items.map((courier) => (
                  <Box
                    key={courier.courier_id}
                    sx={{
                      borderRadius: 1,
                      border: '1px solid',
                      borderColor:
                        selectedCourier?.courier_id === courier.courier_id ? 'primary.main' : 'divider',
                      p: 1,
                      mb: 1,
                      cursor: 'pointer',
                    }}
                    onClick={() => setSelectedCourier(courier)}
                  >
                    <Typography variant="body2">
                      {courier.name} · {courier.status}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Заказов за смену: {courier.orders_delivered_today} · Текущих: {courier.current_orders.length}
                    </Typography>
                  </Box>
                ))}
              </Box>
              <Box flex={1}>
                <Typography variant="subtitle2" gutterBottom>
                  Причина override
                </Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap" mb={1}>
                  {['Курьер уже на месте', 'Знаю маршрут лучше', 'Клиент попросил'].map((preset) => (
                    <Chip
                      key={preset}
                      label={preset}
                      size="small"
                      onClick={() => setOverrideReason(preset)}
                      sx={{ mb: 1 }}
                    />
                  ))}
                </Stack>
                <TextField
                  label="Комментарий"
                  multiline
                  minRows={3}
                  fullWidth
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                />
              </Box>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog} disabled={assignMutation.isLoading}>
            Отмена
          </Button>
          <Button
            variant="contained"
            onClick={handleAssign}
            disabled={!selectedCourier || assignMutation.isLoading}
          >
            {assignMutation.isLoading ? 'Назначаем…' : 'Назначить вручную'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default KitchenOrdersPage;
