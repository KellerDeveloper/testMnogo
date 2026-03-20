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
              <Stack spacing={1} mb={2}>
                <Typography variant="h6">
                  Исполнитель: {detailQuery.data.assigned_to} ({detailQuery.data.carrier_type})
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Источник: {detailQuery.data.assignment_source} • Winner score: {detailQuery.data.winner_score.toFixed(2)} • Версия: {detailQuery.data.algorithm_version}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {detailQuery.data.reason_summary}
                </Typography>
              </Stack>

              <Box mt={2}>
                <Typography variant="subtitle2" gutterBottom>
                  Факторы победителя
                </Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Фактор</TableCell>
                      <TableCell>Оценка</TableCell>
                      <TableCell>Вес</TableCell>
                      <TableCell>Вклад</TableCell>
                      <TableCell>Пояснение</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(() => {
                      const factorsComponentTotal = (detailQuery.data.factors ?? []).reduce(
                        (sum, f) => sum + (f.normalized_value ?? 0) * (f.weight ?? 0),
                        0,
                      );
                      return detailQuery.data.factors.map((f) => {
                      const factorLabels: Record<string, string> = {
                        delivery_time: 'Время до дедлайна',
                        fairness: 'Справедливость загрузки',
                        distance: 'Близость к кухне',
                        batch: 'Совместимость с активностью',
                        geo_trust: 'Доверие к гео',
                      };
                      const factorLabel = factorLabels[f.name] ?? f.name;

                      const normalizedPercent = Math.round((f.normalized_value ?? 0) * 100);
                      const weightPercent = Math.round((f.weight ?? 0) * 100);
                      const contributionShare =
                        factorsComponentTotal > 0 ? ((f.normalized_value ?? 0) * (f.weight ?? 0)) / factorsComponentTotal : 0;
                      const contributionPercent = Math.round(contributionShare * 100);

                      let rawHint: string | null = null;
                      if (f.raw_value !== null && f.raw_value !== undefined) {
                        if (typeof f.raw_value === 'number') {
                          if (f.name === 'delivery_time') rawHint = `ETA: ${f.raw_value.toFixed(0)} мин`;
                          else rawHint = `Значение: ${f.raw_value}`;
                        } else {
                          rawHint = `Значение: ${String(f.raw_value)}`;
                        }
                      }

                      return (
                        <TableRow key={f.name}>
                          <TableCell>
                            <Stack spacing={0.25}>
                              <Typography variant="body2" fontWeight={600}>
                                {factorLabel}
                              </Typography>
                              {rawHint && (
                                <Typography variant="caption" color="text.secondary">
                                  {rawHint}
                                </Typography>
                              )}
                            </Stack>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">{normalizedPercent}%</Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">{weightPercent}%</Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">{contributionPercent}%</Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" color="text.secondary" style={{ whiteSpace: 'pre-wrap' }}>
                              {f.explanation}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      );
                      });
                    })()}
                  </TableBody>
                </Table>
              </Box>

              <Box mt={3}>
                <Typography variant="subtitle2" gutterBottom>
                  Оценки кандидатов (top)
                </Typography>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Кандидат</TableCell>
                      <TableCell align="right">Score</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {Object.entries(detailQuery.data.scores ?? {})
                      .map(([id, score]) => ({ id, score }))
                      .sort((a, b) => b.score - a.score)
                      .slice(0, 10)
                      .map((row) => (
                        <TableRow key={row.id}>
                          <TableCell>
                            <Stack direction="row" spacing={1} alignItems="center">
                              <Typography variant="body2" fontWeight={row.id === detailQuery.data.assigned_to ? 700 : 400}>
                                {row.id}
                              </Typography>
                              {row.id === detailQuery.data.assigned_to && <Chip size="small" label="Победитель" color="primary" />}
                            </Stack>
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2">{row.score.toFixed(2)}</Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </Box>

              {Object.keys(detailQuery.data.context_snapshot ?? {}).length > 0 && (() => {
                const ctx = detailQuery.data.context_snapshot ?? {};
                const candidateCount = ctx.candidate_count;
                const staffCount = ctx.staff_count;
                const threePlCount = ctx['3pl_count'];
                const orderId = ctx.order_id;
                const kitchenId = ctx.kitchen_id;

                return (
                  <Box mt={3}>
                    <Typography variant="subtitle2" gutterBottom>
                      Контекст
                    </Typography>
                    <Stack spacing={0.5}>
                      {candidateCount !== undefined && (
                        <Typography variant="body2" color="text.secondary">
                          Кандидатов: {String(candidateCount)}
                        </Typography>
                      )}
                      {staffCount !== undefined && (
                        <Typography variant="body2" color="text.secondary">
                          Staff: {String(staffCount)}
                        </Typography>
                      )}
                      {threePlCount !== undefined && (
                        <Typography variant="body2" color="text.secondary">
                          3PL: {String(threePlCount)}
                        </Typography>
                      )}
                      {(orderId || kitchenId) && (
                        <Typography variant="body2" color="text.secondary">
                          Order: {String(orderId ?? '-')} • Kitchen: {String(kitchenId ?? '-')}
                        </Typography>
                      )}
                    </Stack>
                  </Box>
                );
              })()}
            </Box>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
};

export default OfficeDecisionsPage;
