import React from 'react';
import { Box, Typography, Card, CardContent, CircularProgress, Alert, Button } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { getOverrideRate } from '../../api/logApi';

const OfficeAnalyticsPage: React.FC = () => {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['overrideRate'],
    queryFn: getOverrideRate,
    refetchInterval: 15_000,
    refetchOnWindowFocus: true,
  });

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={2} mb={2}>
        <Box>
          <Typography variant="h5" gutterBottom>
            Override Analytics
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Доля ручных переопределений решений диспатчера.
          </Typography>
        </Box>
        <Button variant="outlined" size="small" onClick={() => refetch()} disabled={isLoading}>
          Обновить
        </Button>
      </Box>
      {isLoading && (
        <Box display="flex" justifyContent="center" mt={4}>
          <CircularProgress />
        </Box>
      )}

      {error && (
        <Alert severity="error">Не удалось загрузить override rate.</Alert>
      )}

      {data && (
        <Card sx={{ maxWidth: 420 }}>
          <CardContent>
            <Typography variant="subtitle1">Override rate</Typography>
            <Typography variant="h4">
              {(data.override_rate * 100).toFixed(1)}%
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {data.overrides} / {data.total} решений
            </Typography>
            {data.alert && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                Внимание: override rate выше порога (15%).
              </Alert>
            )}
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default OfficeAnalyticsPage;
