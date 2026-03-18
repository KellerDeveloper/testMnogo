import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#ff7f50',
    },
    secondary: {
      main: '#0066cc',
    },
    background: {
      default: '#f5f5f7',
    },
  },
  shape: {
    borderRadius: 10,
  },
});
