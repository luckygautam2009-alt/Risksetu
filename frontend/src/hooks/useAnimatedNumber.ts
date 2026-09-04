import { useEffect, useRef, useState } from 'react';

export function useAnimatedNumber(target: number, duration = 450, active = true): number {
  const [value, setValue] = useState(active ? 0 : target);
  const prevTargetRef = useRef(target);

  useEffect(() => {
    if (!active) {
      return;
    }

    // Reset to 0 only on first frame to avoid synchronous setState in effect body
    const needsReset = prevTargetRef.current !== target;
    prevTargetRef.current = target;

    let start: number | null = null;
    let frameId = 0;

    const tick = (now: number) => {
      if (start === null) {
        start = now;
        if (needsReset) {
          setValue(0);
        }
      }
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - (1 - progress) ** 3;
      setValue(target * eased);

      if (progress < 1) {
        frameId = requestAnimationFrame(tick);
      }
    };

    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, [target, duration, active]);

  return value;
}
