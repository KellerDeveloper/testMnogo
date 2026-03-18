import React, { useState } from 'react';
import { Box, Typography, TextField, Stack, Button, Alert } from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { sendCourierFeedback } from '../../api/courierApi';

const CourierSettingsPage: React.FC = () => {
  const [courierId, setCourierId] = useState('');
  const [reason, setReason] = useState('unfair');
  const [comment, setComment] = useState('');
  const [sent, setSent] = useState(false);

  const mutation = useMutation({
    mutationFn: () => sendCourierFeedback(courierId, { reason, comment: comment || undefined }),
    onSuccess: () => {
      setSent(true);
      setComment('');
    },
  });

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Настройки и обратная связь
      </Typography>
      <Typography variant="body2" color="text.secondary" mb={2}>
        Здесь курьер может поделиться обратной связью о справедливости распределения.
      </Typography>

      <Stack spacing={2} maxWidth={480}>
        <TextField
          label="Courier ID"
          size="small"
          value={courierId}
          onChange={(e) => setCourierId(e.target.value)}
        />
        <TextField
          label="Причина (например: unfair, routes, other)"
          size="small"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <TextField
          label="Комментарий"
          multiline
          minRows={3}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
        <Button
          variant="contained"
          onClick={() => mutation.mutate()}
          disabled={!courierId || mutation.isLoading}
        >
          Отправить feedback
        </Button>
        {sent && !mutation.isLoading && (
          <Alert severity="success">Спасибо, обратная связь отправлена.</Alert>
        )}
      </Stack>
    </Box>
  );
};

export default CourierSettingsPage;
