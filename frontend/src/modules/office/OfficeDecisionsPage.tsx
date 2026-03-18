import React, { useState } from 'react';
import {
  Box,
  Stack,
  Typography,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Chip,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  CircularProgress,
  Alert,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
} from '@mui/material';
import { useQuery, useQueries } from '@tanstack/react-query';
import { listDecisions, DispatchDecisionListItem, getDecision } from '../../api/logApi';
import { fetchCourier } from '../../api/courierApi';

const OfficeDecisionsPage: React.FC = () => {
  const [sourceFilter, setSourceFilter] = useState<string>('');
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null);

  const decisionsQuery = useQuery({
    queryKey: ['decisions', sourceFilter],
    queryFn: () => listDecisions({ assignment_source: sourceFilter || undefined, limit: 50 }),
    refetchInterval: 15_000,
    refetchOnWindowFocus: true,
  });

  const uniqueAssignedTo = React.useMemo(() => {
    const ids = decisionsQuery.data?.items?.map((d: DispatchDecisionListItem) => d.assigned_to) ?? [];
    return Array.from(new Set(ids)).filter(Boolean);
  }, [decisionsQuery.data?.items]);

  const courierQueries = useQueries({
    queries: uniqueAssignedTo.map((id) => ({
      queryKey: ['courier', id],
      queryFn: () => fetchCourier(id),
      enabled: !!id,
    })),
  });
  const assignedToName = React.useMemo(() => {
    const m = new Map<string, string>();
    courierQueries.forEach((q, i) => {
      if (q.data?.name && uniqueAssignedTo[i]) m.set(uniqueAssignedTo[i], q.data.name);
    });
    return m;
  }, [courierQueries, uniqueAssignedTo]);

  const detailQuery = useQuery({
    queryKey: ['decision', selectedDecisionId],
    queryFn: () => getDecision(selectedDecisionId as string),
    enabled: !!selectedDecisionId,
  });

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3} spacing={2}>
        <Box>
          <Typography variant="h5" gutterBottom>
            Таймлайн решений диспатчера
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Последние решения с возможностью посмотреть детали скоринга.
          </Typography>
        </Box>
        <Stack direction="row" spacing={2} alignItems="center">
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel id="src-label">Источник назначения</InputLabel>
            <Select
              labelId="src-label"
              label="Источник назначения"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
            >
              <MenuItem value="">Все</MenuItem>
              <MenuItem value="dispatcher_auto">Авто</MenuItem>
              <MenuItem value="manual_override">Ручное</MenuItem>
            </Select>
          </FormControl>
          <Button
            variant="outlined"
            size="small"
            onClick={() => decisionsQuery.refetch()}
            disabled={decisionsQuery.isFetching}
          >
            Обновить
          </Button>
        </Stack>
      </Stack>

      {decisionsQuery.isLoading && (
        <Box display="flex" justifyContent="center" mt={4}>
          <CircularProgress />
        </Box>
      )}

      {decisionsQuery.error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Не удалось загрузить решения.
        </Alert>
      )}

      {decisionsQuery.data && (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Время</TableCell>
              <TableCell>Order</TableCell>
              <TableCell>Исполнитель</TableCell>
              <TableCell>Тип</TableCell>
              <TableCell>Score</TableCell>
              <TableCell align="right">Детали</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {decisionsQuery.data.items.map((d: DispatchDecisionListItem) => (
              <TableRow key={d.decision_id} hover>
                <TableCell>{d.timestamp}</TableCell>
                <TableCell>{d.order_id}</TableCell>
                <TableCell>{assignedToName.get(d.assigned_to) ?? d.assigned_to}</TableCell>
                <TableCell>
                  <Chip
                    label={d.assignment_source}
                    size="small"
                    color={d.assignment_source === 'manual_override' ? 'warning' : 'default'}
                  />
                </TableCell>
                <TableCell>{d.winner_score.toFixed(2)}</TableCell>
                <TableCell align="right">
                  <Button size="small" onClick={() => setSelectedDecisionId(d.decision_id)}>
                    Открыть
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog
        open={!!selectedDecisionId}
        onClose={() => setSelectedDecisionId(null)}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle>Детали решения</DialogTitle>
        <DialogContent dividers>
          {detailQuery.isLoading && (
            <Box display="flex" justifyContent="center" my={2}>
              <CircularProgress size={24} />
            </Box>
          )}
          {detailQuery.data && (
            <Box>
              <Typography variant="subtitle1" gutterBottom>
                {detailQuery.data.reason_summary}
              </Typography>
              <Typography variant="subtitle2" gutterBottom>
                Версия алгоритма: {detailQuery.data.algorithm_version}
              </Typography>
              <Box mt={2}>
                <Typography variant="subtitle2">Scores</Typography>
                <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 8 }}>
                  {JSON.stringify(detailQuery.data.scores, null, 2)}
                </pre>
              </Box>
              <Box mt={2}>
                <Typography variant="subtitle2">Факторы</Typography>
                <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 8 }}>
                  {JSON.stringify(detailQuery.data.factors, null, 2)}
                </pre>
              </Box>
            </Box>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
};

export default OfficeDecisionsPage;
