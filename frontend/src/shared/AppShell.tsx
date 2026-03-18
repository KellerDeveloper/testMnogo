import React from 'react';
import { AppBar, Box, Container, Toolbar, Typography, Button, Stack } from '@mui/material';
import { Link as RouterLink, useLocation } from 'react-router-dom';

interface Props {
  children: React.ReactNode;
}

const AppShell: React.FC<Props> = ({ children }) => {
  const location = useLocation();
  const isKitchen = location.pathname.startsWith('/kitchen');
  const isOffice = location.pathname.startsWith('/office');

  const mainTabs = [
    { to: '/kitchen/orders', label: 'Кухня' },
    { to: '/office/decisions', label: 'Офис' },
  ];

  const kitchenSub = [
    { to: '/kitchen/orders', label: 'Очередь заказов' },
    { to: '/kitchen/orders/create', label: 'Создать заказ' },
    { to: '/kitchen/couriers', label: 'Курьеры' },
  ];
  const officeSub = [
    { to: '/office/decisions', label: 'Решения' },
    { to: '/office/analytics', label: 'Аналитика' },
    { to: '/office/configs', label: 'Конфиги' },
    { to: '/office/couriers', label: 'Курьеры' },
  ];
  const subNav = isKitchen ? kitchenSub : isOffice ? officeSub : [];

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="static" color="primary" elevation={1}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Диспатчер
          </Typography>
          {mainTabs.map((tab) => (
            <Button
              key={tab.to}
              color={location.pathname.startsWith(tab.to) ? 'inherit' : 'secondary'}
              component={RouterLink}
              to={tab.to}
              sx={{ ml: 1 }}
            >
              {tab.label}
            </Button>
          ))}
        </Toolbar>
        {subNav.length > 0 && (
          <Toolbar variant="dense" sx={{ pt: 0, minHeight: 36 }}>
            <Stack direction="row" spacing={0.5}>
              {subNav.map((item) => (
                <Button
                  key={item.to}
                  size="small"
                  component={RouterLink}
                  to={item.to}
                  color={location.pathname === item.to ? 'inherit' : 'secondary'}
                  sx={{ textTransform: 'none' }}
                >
                  {item.label}
                </Button>
              ))}
            </Stack>
          </Toolbar>
        )}
      </AppBar>
      <Container maxWidth="lg" sx={{ py: 3 }}>
        {children}
      </Container>
    </Box>
  );
};

export default AppShell;
