import { createTheme } from '@mui/material/styles';
import { tokens } from './tokens';

const theme = createTheme({
  cssVariables: true,
  palette: {
    mode: 'dark',
    primary: {
      main: tokens.colors.brand.primary,
      light: tokens.colors.brand.primaryLight,
      dark: tokens.colors.brand.primaryDark,
    },
    secondary: {
      main: tokens.colors.brand.secondary,
      light: tokens.colors.brand.secondaryLight,
      dark: tokens.colors.brand.secondaryDark,
    },
    background: {
      default: '#000000', // 纯黑（官网风格）
      paper: tokens.colors.surface.glass,
    },
    success: {
      main: tokens.colors.semantic.success,
      light: tokens.colors.semantic.successLight,
    },
    error: {
      main: tokens.colors.semantic.error,
      light: tokens.colors.semantic.errorLight,
    },
    warning: {
      main: tokens.colors.semantic.warning,
      light: tokens.colors.semantic.warningLight,
    },
    info: {
      main: tokens.colors.semantic.info,
      light: tokens.colors.semantic.infoLight,
    },
    text: {
      primary: tokens.colors.text.primary,
      secondary: tokens.colors.text.secondary,
      disabled: tokens.colors.text.disabled,
    },
    divider: tokens.colors.border.default,
  },
  typography: {
    fontFamily: tokens.typography.fontFamily.base,
    fontSize: 15, // 基础字号
    h1: {
      fontFamily: tokens.typography.fontFamily.display,
      fontWeight: tokens.typography.fontWeight.bold,
      letterSpacing: tokens.typography.letterSpacing.tight,
      lineHeight: tokens.typography.lineHeight.tight,
    },
    h2: {
      fontFamily: tokens.typography.fontFamily.display,
      fontWeight: tokens.typography.fontWeight.bold,
      letterSpacing: tokens.typography.letterSpacing.tight,
      lineHeight: tokens.typography.lineHeight.tight,
    },
    h3: {
      fontWeight: tokens.typography.fontWeight.semibold,
      letterSpacing: tokens.typography.letterSpacing.tight,
      lineHeight: tokens.typography.lineHeight.snug,
    },
    h4: {
      fontWeight: tokens.typography.fontWeight.semibold,
      letterSpacing: tokens.typography.letterSpacing.normal,
      lineHeight: tokens.typography.lineHeight.snug,
    },
    h5: {
      fontWeight: tokens.typography.fontWeight.medium,
      lineHeight: tokens.typography.lineHeight.normal,
    },
    h6: {
      fontWeight: tokens.typography.fontWeight.medium,
      lineHeight: tokens.typography.lineHeight.normal,
    },
    body1: {
      lineHeight: tokens.typography.lineHeight.relaxed,
    },
    body2: {
      lineHeight: tokens.typography.lineHeight.normal,
    },
  },
  shape: {
    borderRadius: 10,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          background: 'linear-gradient(135deg, #0f0c29 0%, #1a1a2e 50%, #16213e 100%)',
          backgroundAttachment: 'fixed',
          overflow: 'auto',
          WebkitFontSmoothing: 'antialiased',
          MozOsxFontSmoothing: 'grayscale',
        },
        '::-webkit-scrollbar': {
          width: 8,
          height: 8,
        },
        '::-webkit-scrollbar-track': {
          background: tokens.colors.scrollbar.track,
        },
        '::-webkit-scrollbar-thumb': {
          background: tokens.colors.scrollbar.thumb,
          borderRadius: tokens.borderRadius.base,
          '&:hover': {
            background: tokens.colors.scrollbar.thumbHover,
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backdropFilter: tokens.effects.backdropBlur.base,
          backgroundColor: tokens.colors.surface.glass,
          border: `1px solid ${tokens.colors.border.default}`,
          boxShadow: tokens.shadows.sm,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backdropFilter: tokens.effects.backdropBlur.base,
          backgroundColor: tokens.colors.surface.card,
          border: `1px solid ${tokens.colors.border.default}`,
          boxShadow: tokens.shadows.sm,
          transition: `all ${tokens.transitions.duration.base} ${tokens.transitions.easing.default}`,
          '&:hover': {
            backgroundColor: tokens.colors.surface.cardHover,
            borderColor: tokens.colors.border.medium,
            boxShadow: tokens.shadows.md,
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: tokens.typography.fontWeight.medium,
          borderRadius: tokens.borderRadius.lg,
          fontSize: tokens.typography.fontSize.sm,
          letterSpacing: tokens.typography.letterSpacing.wide,
          transition: `all ${tokens.transitions.duration.fast} ${tokens.transitions.easing.default}`,
        },
        contained: {
          background: tokens.colors.gradient.primary,
          boxShadow: tokens.shadows.sm,
          '&:hover': {
            background: tokens.colors.gradient.primaryHover,
            boxShadow: tokens.shadows.glowSubtle,
            transform: 'translateY(-1px)',
          },
          '&:active': {
            transform: 'translateY(0)',
          },
        },
        outlined: {
          borderColor: tokens.colors.border.strong,
          borderWidth: '1.5px',
          '&:hover': {
            borderColor: tokens.colors.brand.primary,
            backgroundColor: tokens.colors.interaction.hover,
            borderWidth: '1.5px',
          },
        },
        text: {
          '&:hover': {
            backgroundColor: tokens.colors.interaction.hover,
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            backgroundColor: tokens.colors.surface.glass,
            transition: `all ${tokens.transitions.duration.fast} ${tokens.transitions.easing.default}`,
            '& fieldset': {
              borderColor: tokens.colors.border.default,
              transition: `border-color ${tokens.transitions.duration.fast}`,
            },
            '&:hover fieldset': {
              borderColor: tokens.colors.border.medium,
            },
            '&.Mui-focused': {
              backgroundColor: tokens.colors.surface.elevated,
              '& fieldset': {
                borderColor: tokens.colors.brand.primary,
                borderWidth: '1.5px',
              },
            },
          },
          '& .MuiInputLabel-root': {
            fontSize: tokens.typography.fontSize.sm,
            '&.Mui-focused': {
              color: tokens.colors.brand.primary,
            },
          },
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          '& .MuiTableCell-head': {
            fontWeight: tokens.typography.fontWeight.semibold,
            fontSize: tokens.typography.fontSize.xs,
            textTransform: 'uppercase',
            letterSpacing: tokens.typography.letterSpacing.wider,
            color: tokens.colors.text.tertiary,
            borderBottomColor: tokens.colors.border.medium,
            backgroundColor: tokens.colors.overlay.light,
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottomColor: tokens.colors.border.subtle,
          fontSize: tokens.typography.fontSize.sm,
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: `background-color ${tokens.transitions.duration.fast}`,
          '&:hover': {
            backgroundColor: `${tokens.colors.interaction.hover} !important`,
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: tokens.typography.fontWeight.medium,
          fontSize: tokens.typography.fontSize.xs,
          letterSpacing: tokens.typography.letterSpacing.wide,
          borderRadius: tokens.borderRadius.base,
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          backdropFilter: tokens.effects.backdropBlur.lg,
          backgroundColor: tokens.colors.surface.elevated,
          border: `1px solid ${tokens.colors.border.medium}`,
          boxShadow: tokens.shadows.xl,
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backdropFilter: tokens.effects.backdropBlur.xl,
          backgroundColor: tokens.colors.surface.drawer,
          borderRight: `1px solid ${tokens.colors.border.subtle}`,
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backdropFilter: tokens.effects.backdropBlur.xl,
          backgroundColor: tokens.colors.surface.appBar,
          borderBottom: `1px solid ${tokens.colors.border.subtle}`,
          boxShadow: 'none',
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: tokens.typography.fontWeight.medium,
          fontSize: tokens.typography.fontSize.sm,
          letterSpacing: tokens.typography.letterSpacing.wide,
          minHeight: 44,
          transition: `all ${tokens.transitions.duration.fast}`,
          '&:hover': {
            color: tokens.colors.text.primary,
          },
        },
      },
    },
    MuiTabs: {
      styleOverrides: {
        indicator: {
          background: tokens.colors.gradient.primary,
          height: 2,
          borderRadius: tokens.borderRadius.full,
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          borderRadius: tokens.borderRadius.lg,
          transition: `all ${tokens.transitions.duration.fast}`,
          '&:hover': {
            backgroundColor: tokens.colors.interaction.hover,
          },
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          backgroundColor: tokens.colors.surface.elevated,
          border: `1px solid ${tokens.colors.border.medium}`,
          backdropFilter: tokens.effects.backdropBlur.base,
          fontSize: tokens.typography.fontSize.xs,
          padding: `${tokens.spacing[2]} ${tokens.spacing[3]}`,
          borderRadius: tokens.borderRadius.md,
          boxShadow: tokens.shadows.lg,
        },
        arrow: {
          color: tokens.colors.surface.elevated,
          '&::before': {
            border: `1px solid ${tokens.colors.border.medium}`,
          },
        },
      },
    },
    MuiSnackbar: {
      styleOverrides: {
        root: {
          '& .MuiPaper-root': {
            backdropFilter: tokens.effects.backdropBlur.lg,
            backgroundColor: tokens.colors.surface.elevated,
            border: `1px solid ${tokens.colors.border.medium}`,
            boxShadow: tokens.shadows.xl,
          },
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: tokens.borderRadius.lg,
          fontSize: tokens.typography.fontSize.sm,
        },
      },
    },
    MuiSwitch: {
      styleOverrides: {
        root: {
          '& .MuiSwitch-switchBase.Mui-checked': {
            color: tokens.colors.brand.primary,
            '& + .MuiSwitch-track': {
              backgroundColor: tokens.colors.brand.primary,
              opacity: 0.5,
            },
          },
        },
      },
    },
  },
});

export default theme;
