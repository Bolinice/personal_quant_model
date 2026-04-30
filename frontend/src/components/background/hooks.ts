import { useContext } from 'react';
import { BackgroundContext } from './BackgroundContext';

export function useBackground() {
  return useContext(BackgroundContext);
}
