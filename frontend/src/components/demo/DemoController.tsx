import { useEffect, useRef, useCallback } from 'react';
import { useMapContext, type DemoStep } from '../../context/MapContext';
import './DemoController.css';

interface DemoStepMeta {
  step: DemoStep;
  label: string;
  phase: string;
}

const DEMO_STEPS: DemoStepMeta[] = [
  { step: 0, label: 'Initializing', phase: 'SYSTEM' },
  { step: 1, label: 'Select Chamoli — Critical Zone', phase: 'HAZARD' },
  { step: 2, label: 'Risk Score Computed — 98.9 CRITICAL', phase: 'RISK' },
  { step: 3, label: 'Evidence Analysis — Why This Location?', phase: 'WHY' },
  { step: 4, label: 'Road Failure Simulation Initiated', phase: 'IMPACT' },
  { step: 5, label: 'Network Topology Fragmented', phase: 'IMPACT' },
  { step: 6, label: 'Intervention Priority Ranked', phase: 'PRIORITY' },
  { step: 7, label: 'Ground Intelligence Detected', phase: 'INTEL' },
  { step: 8, label: 'Critical Alert — Immediate Action Required', phase: 'ALERT' },
  { step: 9, label: 'Demo Complete', phase: 'END' },
];

// Duration each step holds before advancing (ms)
const STEP_DURATIONS: Record<DemoStep, number> = {
  0: 800,   // init
  1: 2200,  // select chamoli + fly
  2: 2000,  // risk animates
  3: 2800,  // evidence bars
  4: 1200,  // start sim
  5: 3500,  // sim result renders
  6: 2500,  // priority
  7: 2800,  // ground intel
  8: 3000,  // alert
  9: 0,     // end (no auto advance)
};

export function DemoController() {
  const {
    isDemoRunning,
    demoStep,
    startDemo,
    stopDemo,
    setDemoStep,
    selectHazard,
    startSimulation,
    setWorkflowTab,
    selectObservation,
    selectAlert,
    selectPriority,
  } = useMapContext();

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isRunningRef = useRef(isDemoRunning);
  useEffect(() => {
    isRunningRef.current = isDemoRunning;
  }, [isDemoRunning]);

  // Execute the action for each step
  const executeStep = useCallback((step: DemoStep) => {
    switch (step) {
      case 0:
        // Reset done in startDemo
        break;
      case 1:
        setWorkflowTab('risk');
        selectHazard('hz-chamoli');
        break;
      case 2:
        // Risk score animation plays automatically via FloatingLocationPanel
        break;
      case 3:
        // Evidence bars animate automatically
        break;
      case 4:
        startSimulation('road-nh58');
        break;
      case 5:
        // Simulation result renders automatically — switch to impact tab for emphasis
        setWorkflowTab('impact');
        break;
      case 6:
        setWorkflowTab('priority');
        selectPriority('prio-chamoli');
        break;
      case 7:
        selectObservation('obs-chamoli-01');
        break;
      case 8:
        selectAlert('alert-chamoli-01');
        break;
      case 9:
        // Done — leave state as-is
        break;
    }
  }, [selectHazard, startSimulation, setWorkflowTab, selectPriority, selectObservation, selectAlert]);

  // Advance demo step by step
  useEffect(() => {
    if (!isDemoRunning || demoStep === 9) return;

    executeStep(demoStep);

    const duration = STEP_DURATIONS[demoStep];
    timerRef.current = setTimeout(() => {
      if (isRunningRef.current) {
        const next = (demoStep + 1) as DemoStep;
        setDemoStep(next);
      }
    }, duration);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isDemoRunning, demoStep, executeStep, setDemoStep]);

  const currentMeta = DEMO_STEPS[demoStep] ?? DEMO_STEPS[0];
  const progress = demoStep === 9 ? 100 : Math.round((demoStep / 9) * 100);

  // The launch button (shown when not running)
  if (!isDemoRunning) {
    return (
      <div className="demo-launch" aria-label="Demo Mode launcher">
        <button
          type="button"
          className="demo-launch__btn"
          onClick={startDemo}
          title="Run full intelligence demonstration"
        >
          <span className="demo-launch__icon" aria-hidden="true">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          </span>
          <span className="demo-launch__label font-mono">DEMO</span>
        </button>
      </div>
    );
  }

  // The active demo HUD ribbon
  return (
    <>
      {/* Full-width demo ribbon at top of map */}
      <div className="demo-hud" role="status" aria-live="polite" aria-label="Demo mode progress">
        <div className="demo-hud__inner">
          {/* Left: Live step label */}
          <div className="demo-hud__info">
            <span className="demo-hud__tag font-mono">
              <span className="demo-hud__tag-dot" aria-hidden="true" />
              DEMO MODE
            </span>
            <span className="demo-hud__phase font-mono">{currentMeta.phase}</span>
            <span className="demo-hud__label">{currentMeta.label}</span>
          </div>

          {/* Center: Step dots */}
          <div className="demo-hud__steps" aria-label="Demo steps">
            {DEMO_STEPS.slice(1).map((s) => (
              <button
                key={s.step}
                type="button"
                className={`demo-hud__dot ${
                  demoStep === s.step
                    ? 'demo-hud__dot--active'
                    : demoStep > s.step
                    ? 'demo-hud__dot--done'
                    : ''
                }`}
                onClick={() => {
                  if (timerRef.current) clearTimeout(timerRef.current);
                  setDemoStep(s.step);
                }}
                title={`Jump to: ${s.label}`}
                aria-label={`Step ${s.step}: ${s.label}`}
              />
            ))}
          </div>

          {/* Right: Progress + stop */}
          <div className="demo-hud__controls">
            <span className="demo-hud__progress font-mono">{String(demoStep).padStart(2, '0')}/09</span>
            <button
              type="button"
              className="demo-hud__stop"
              onClick={stopDemo}
              title="Exit demo mode"
              aria-label="Stop demo"
            >
              <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
                <rect x="3" y="3" width="18" height="18" rx="2" />
              </svg>
            </button>
          </div>
        </div>

        {/* Progress bar */}
        <div className="demo-hud__bar">
          <div
            className="demo-hud__bar-fill"
            style={{ width: `${progress}%` }}
            aria-hidden="true"
          />
        </div>
      </div>

      {/* Floating step counter (bottom-left) */}
      <div className="demo-launch" aria-hidden="true">
        <button
          type="button"
          className="demo-launch__btn demo-launch__btn--active"
          onClick={stopDemo}
          title="Exit demo mode"
        >
          <span className="demo-launch__icon" aria-hidden="true">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
              <rect x="3" y="3" width="18" height="18" rx="2" />
            </svg>
          </span>
          <span className="demo-launch__label font-mono">EXIT DEMO</span>
        </button>
      </div>
    </>
  );
}
