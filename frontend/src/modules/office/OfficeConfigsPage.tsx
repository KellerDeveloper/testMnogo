import React, { useState } from 'react';
import {
  Box,
  Typography,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  CircularProgress,
  Alert,
  Switch,
  FormControlLabel,
  Paper,
  Stack,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listConfigs, updateConfig, assignConfigToKitchen, createConfig, AlgorithmConfig } from '../../api/configApi';

const DEFAULT_KITCHEN_ID = '11111111-1111-1111-1111-111111111111';

const OfficeConfigsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [newVersion, setNewVersion] = useState<string>('v1.0');
  const [newName, setNewName] = useState<string>('default');
  const [newDescription, setNewDescription] = useState<string>('');
  const [newCreatedBy, setNewCreatedBy] = useState<string>('test');
  const [assignConfigId, setAssignConfigId] = useState<string>('');
  const [assignKitchenId, setAssignKitchenId] = useState<string>(DEFAULT_KITCHEN_ID);

  const { data, isLoading, error } = useQuery({
    queryKey: ['algorithmConfigs'],
    queryFn: () => listConfigs(false),
  });

  const activateMutation = useMutation({
    mutationFn: ({ configId, isActive }: { configId: string; isActive: boolean }) =>
      updateConfig(configId, { is_active: isActive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['algorithmConfigs'] });
    },
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createConfig({
        version: newVersion.trim(),
        name: newName.trim(),
        description: newDescription.trim() || undefined,
        created_by: newCreatedBy.trim() || 'unknown',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['algorithmConfigs'] });
      setNewDescription('');
    },
  });

  const assignMutation = useMutation({
    mutationFn: () => assignConfigToKitchen(assignConfigId, assignKitchenId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['algorithmConfigs'] });
    },
  });

  const handleToggleActive = (cfg: AlgorithmConfig) => {
    activateMutation.mutate({ configId: cfg.config_id, isActive: !cfg.is_active });
  };

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" flexWrap="wrap" gap={2} mb={2}>
        <Box>
          <Typography variant="h5" gutterBottom>
            Конфигурации алгоритмов
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Список версий алгоритма диспатчеризации. Включите переключатель, чтобы активировать конфиг. Привяжите конфиг к кухне — тогда диспатчер будет использовать его для заказов этой кухни.
          </Typography>
        </Box>
        <Button
          variant="contained"
          color="primary"
          onClick={() => createMutation.mutate()}
          disabled={!newVersion.trim() || !newName.trim() || createMutation.isPending}
        >
          {createMutation.isPending ? <CircularProgress size={24} /> : 'Создать конфиг'}
        </Button>
      </Stack>

      <Paper sx={{ p: 2, mb: 3, maxWidth: 640 }}>
        <Typography variant="subtitle1" gutterBottom>
          Создать новый конфиг
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Укажите версию, название и автора. Веса и параметры по умолчанию будут проставлены на бэкенде; при необходимости их можно потом отредактировать через API.
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="flex-start" mb={2}>
          <TextField
            label="Версия"
            size="small"
            value={newVersion}
            onChange={(e) => setNewVersion(e.target.value)}
            sx={{ minWidth: 120 }}
          />
          <TextField
            label="Название"
            size="small"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            sx={{ minWidth: 180 }}
          />
          <TextField
            label="Автор (created_by)"
            size="small"
            value={newCreatedBy}
            onChange={(e) => setNewCreatedBy(e.target.value)}
            sx={{ minWidth: 160 }}
          />
        </Stack>
        <TextField
          label="Описание"
          size="small"
          fullWidth
          multiline
          minRows={2}
          value={newDescription}
          onChange={(e) => setNewDescription(e.target.value)}
          sx={{ mb: 2 }}
        />
        <Button
          variant="contained"
          onClick={() => createMutation.mutate()}
          disabled={!newVersion.trim() || !newName.trim() || createMutation.isPending}
        >
          {createMutation.isPending ? <CircularProgress size={24} /> : 'Создать конфиг'}
        </Button>
        {createMutation.isSuccess && (
          <Alert severity="success" sx={{ mt: 2 }}>
            Конфиг {newVersion} создан.
          </Alert>
        )}
        {createMutation.isError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {(createMutation.error as Error).message}
          </Alert>
        )}
      </Paper>


      <Paper sx={{ p: 2, mb: 3, maxWidth: 560 }}>
        <Typography variant="subtitle1" gutterBottom>
          Привязать конфиг к кухне
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Выберите конфиг и укажите Kitchen ID — после назначения диспатчер будет использовать этот конфиг для заказов данной кухни.
        </Typography>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="flex-start">
          <FormControl size="small" sx={{ minWidth: 220 }}>
            <InputLabel>Конфиг</InputLabel>
            <Select
              label="Конфиг"
              value={assignConfigId}
              onChange={(e) => setAssignConfigId(e.target.value)}
            >
              {data?.items.map((cfg) => (
                <MenuItem key={cfg.config_id} value={cfg.config_id}>
                  {cfg.version} — {cfg.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Kitchen ID"
            size="small"
            value={assignKitchenId}
            onChange={(e) => setAssignKitchenId(e.target.value)}
            sx={{ minWidth: 320 }}
            placeholder="UUID кухни"
          />
          <Button
            variant="contained"
            onClick={() => assignMutation.mutate()}
            disabled={!assignConfigId || !assignKitchenId.trim() || assignMutation.isPending}
          >
            {assignMutation.isPending ? <CircularProgress size={24} /> : 'Назначить'}
          </Button>
        </Stack>
        {assignMutation.isSuccess && (
          <Alert severity="success" sx={{ mt: 2 }}>
            Конфиг назначен кухне {assignKitchenId}.
          </Alert>
        )}
        {assignMutation.isError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {(assignMutation.error as Error).message}
          </Alert>
        )}
      </Paper>

      {isLoading && (
        <Box display="flex" justifyContent="center" mt={4}>
          <CircularProgress />
        </Box>
      )}

      {error && <Alert severity="error">Не удалось загрузить конфигурации.</Alert>}

      {data && (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Версия</TableCell>
              <TableCell>Название</TableCell>
              <TableCell>Активна</TableCell>
              <TableCell>Кухонь</TableCell>
              <TableCell>Создал</TableCell>
              <TableCell>Одобрил</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.items.map((cfg: AlgorithmConfig) => (
              <TableRow key={cfg.config_id}>
                <TableCell>{cfg.version}</TableCell>
                <TableCell>{cfg.name}</TableCell>
                <TableCell>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={cfg.is_active}
                        onChange={() => handleToggleActive(cfg)}
                        disabled={activateMutation.isPending}
                        color="primary"
                      />
                    }
                    label={cfg.is_active ? 'Активна' : 'Неактивна'}
                    labelPlacement="start"
                  />
                </TableCell>
                <TableCell>{cfg.kitchen_ids.length}</TableCell>
                <TableCell>{cfg.created_by}</TableCell>
                <TableCell>{cfg.approved_by || '-'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Box>
  );
};

export default OfficeConfigsPage;
