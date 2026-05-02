import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import Joyride, { Step, CallBackProps, STATUS } from 'react-joyride';
import { tokens } from '@/styles/tokens';

interface OnboardingContextType {
  startTour: (tourName: string) => void;
  resetTour: (tourName: string) => void;
  skipAllTours: () => void;
  isTourCompleted: (tourName: string) => boolean;
}

const OnboardingContext = createContext<OnboardingContextType | undefined>(undefined);

export const useOnboarding = () => {
  const context = useContext(OnboardingContext);
  if (!context) {
    throw new Error('useOnboarding must be used within OnboardingProvider');
  }
  return context;
};

// 引导步骤配置
export const tourSteps: Record<string, Step[]> = {
  dashboard: [
    {
      target: 'body',
      content: '欢迎来到量化投资平台！让我们快速了解一下核心功能。',
      placement: 'center',
      disableBeacon: true,
    },
    {
      target: '[data-tour="quick-links"]',
      content: '这里是快捷入口，可以快速访问各个功能模块。',
      placement: 'top',
    },
  ],
  models: [
    {
      target: '[data-tour="model-filters"]',
      content: '使用筛选器快速找到符合您需求的模型。',
      placement: 'bottom',
    },
    {
      target: '[data-tour="model-card"]',
      content: '每个模型卡片显示关键指标，点击可查看详细信息。',
      placement: 'top',
    },
  ],
};

// 自定义样式
const joyrideStyles = {
  options: {
    primaryColor: tokens.colors.brand.primary,
    textColor: tokens.colors.text.primary,
    backgroundColor: tokens.colors.surface.elevated,
    overlayColor: 'rgba(0, 0, 0, 0.7)',
    arrowColor: tokens.colors.surface.elevated,
    zIndex: tokens.zIndex.modal,
  },
  tooltip: {
    borderRadius: tokens.borderRadius.lg,
    padding: tokens.spacing[6],
    fontSize: tokens.typography.fontSize.base,
  },
  tooltipContainer: {
    textAlign: 'left' as const,
  },
  tooltipTitle: {
    fontSize: tokens.typography.fontSize.lg,
    fontWeight: tokens.typography.fontWeight.semibold,
    marginBottom: tokens.spacing[2],
  },
  tooltipContent: {
    padding: `${tokens.spacing[2]} 0`,
  },
  buttonNext: {
    backgroundColor: tokens.colors.brand.primary,
    borderRadius: tokens.borderRadius.md,
    padding: `${tokens.spacing[2]} ${tokens.spacing[4]}`,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.medium,
  },
  buttonBack: {
    color: tokens.colors.text.secondary,
    marginRight: tokens.spacing[2],
  },
  buttonSkip: {
    color: tokens.colors.text.secondary,
  },
};

interface OnboardingProviderProps {
  children: React.ReactNode;
}

export const OnboardingProvider: React.FC<OnboardingProviderProps> = ({ children }) => {
  const [run, setRun] = useState(false);
  const [steps, setSteps] = useState<Step[]>([]);
  const [currentTour, setCurrentTour] = useState<string>('');

  // 从 localStorage 读取已完成的引导
  const getCompletedTours = (): Set<string> => {
    const stored = localStorage.getItem('completedTours');
    return stored ? new Set(JSON.parse(stored)) : new Set();
  };

  const [completedTours, setCompletedTours] = useState<Set<string>>(getCompletedTours);

  // 保存已完成的引导到 localStorage
  useEffect(() => {
    localStorage.setItem('completedTours', JSON.stringify([...completedTours]));
  }, [completedTours]);

  const startTour = useCallback((tourName: string) => {
    const tourStepsData = tourSteps[tourName];
    if (!tourStepsData) {
      console.warn(`Tour "${tourName}" not found`);
      return;
    }

    // 如果已完成，不再显示
    if (completedTours.has(tourName)) {
      return;
    }

    setCurrentTour(tourName);
    setSteps(tourStepsData);
    setRun(true);
  }, [completedTours]);

  const resetTour = useCallback((tourName: string) => {
    setCompletedTours(prev => {
      const newSet = new Set(prev);
      newSet.delete(tourName);
      return newSet;
    });
    startTour(tourName);
  }, [startTour]);

  const skipAllTours = useCallback(() => {
    const allTourNames = Object.keys(tourSteps);
    setCompletedTours(new Set(allTourNames));
    setRun(false);
  }, []);

  const isTourCompleted = useCallback((tourName: string) => {
    return completedTours.has(tourName);
  }, [completedTours]);

  const handleJoyrideCallback = (data: CallBackProps) => {
    const { status } = data;
    const finishedStatuses: string[] = [STATUS.FINISHED, STATUS.SKIPPED];

    if (finishedStatuses.includes(status)) {
      setRun(false);
      if (currentTour) {
        setCompletedTours(prev => new Set(prev).add(currentTour));
      }
    }
  };

  return (
    <OnboardingContext.Provider
      value={{
        startTour,
        resetTour,
        skipAllTours,
        isTourCompleted,
      }}
    >
      {children}
      <Joyride
        steps={steps}
        run={run}
        continuous
        showProgress
        showSkipButton
        styles={joyrideStyles}
        callback={handleJoyrideCallback}
        locale={{
          back: '上一步',
          close: '关闭',
          last: '完成',
          next: '下一步',
          skip: '跳过',
        }}
      />
    </OnboardingContext.Provider>
  );
};
