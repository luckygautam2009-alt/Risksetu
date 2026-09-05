import { useEffect, useRef, useCallback } from 'react';
import { useMapContext } from '../../context/MapContext';
import './DemoController.css';

interface DemoStepMeta {
  step: number;
  label: string;
  phase: string;
  description: string;
}

const DEMO_STEPS: DemoStepMeta[] = [
  {
    step: 0,
    label: 'Initializing System',
    phase: 'SYSTEM',
    description: 'Loading certified Uttarakhand & Sikkim GIS layers and spatial boundaries.',
  },
  {
    step: 1,
    label: 'Chamoli Corridor Focus',
    phase: 'LOCATION',
    description: 'Centering on high-risk landslide zone along NH-58 corridor.',
  },
  {
    step: 2,
    label: 'Phase 2A Deterministic Risk Engine',
    phase: 'RISK EVAL',
    description: 'Evaluating multi-factor slope, geology, and seismic hazard index via live API.',
  },
  {
    step: 3,
    label: 'Live Weather Synchronization',
    phase: 'WEATHER',
    description: 'Querying real-time precipitation, 72h accumulation, and flash-flood thresholds.',
  },
  {
    step: 4,
    label: 'Catchment Screening Watch',
    phase: 'REGIONAL',
    description: 'Screening upstream catchment precipitation across Alaknanda & Mandakini basins.',
  },
  {
    step: 5,
    label: 'Critical Road Lifeline Selection',
    phase: 'INFRA',
    description: 'Selecting NH-58 Joshimath–Badrinath arterial road segment for analysis.',
  },
  {
    step: 6,
    label: 'Phase 2B Road Failure Simulation',
    phase: 'SIMULATION',
    description: 'Simulating landslide blockage and running PostGIS network graph partitioning.',
  },
  {
    step: 7,
    label: 'Network Topology & Isolation Analysis',
    phase: 'CONNECTIVITY',
    description: 'Quantifying isolated settlements, component increase, and affected population.',
  },
  {
    step: 8,
    label: 'Phase 2C Intervention Priority Ranking',
    phase: 'PRIORITIZATION',
    description: 'Optimizing clearance sequence based on deterministic isolation severity impact.',
  },
  {
    step: 9,
    label: 'Phase 1B Field Ground Intelligence',
    phase: 'INTEL',
    description: 'Ingesting ground truth observation with algorithmic trust score heuristic.',
  },
  {
    step: 10,
    label: 'Community Proximity Verification',
    phase: 'VERIFICATION',
    description: 'Collecting 500m crowd-sourced signal without altering certified engineering state.',
  },
  {
    step: 11,
    label: 'Emergency SOS Dispatch',
    phase: 'SOS DISPATCH',
    description: 'Submitting geocoded citizen distress report with attached live risk context.',
  },
  {
    step: 12,
    label: 'Shelter Availability Protocol',
    phase: 'SHELTER',
    description: 'Honest reporting: certified shelter database query returning verified state.',
  },
  {
    step: 13,
    label: 'Offline-First Resilience (IndexedDB)',
    phase: 'OFFLINE PWA',
    description: 'Local queueing ensures SOS and citizen reports survive complete connectivity loss.',
  },
  {
    step: 14,
    label: 'Officer Mission Control Workspace',
    phase: 'COMMAND HQ',
    description: 'Managing active officer SOS queue, status acknowledgment, and triage.',
  },
  {
    step: 15,
    label: 'OSINT Hazard Intelligence Scanner',
    phase: 'OSINT INTEL',
    description: 'Public hazard feed scanning corroborated with localized precipitation signals.',
  },
  {
    step: 16,
    label: 'Geofenced Mass Broadcast Siren',
    phase: 'MASS ALERT',
    description: 'Simulating geofenced siren broadcast across 1km radius with web audio synthesis.',
  },
];

// Duration each step holds in auto-play before advancing (ms)
const STEP_DURATIONS: Record<number, number> = {
  0: 1200,
  1: 2500,
  2: 3000,
  3: 3500,
  4: 3000,
  5: 2500,
  6: 3500,
  7: 3500,
  8: 3000,
  9: 3000,
  10: 2500,
  11: 3500,
  12: 3000,
  13: 2500,
  14: 3500,
  15: 3500,
  16: 4000,
};

export function DemoController() {
  const {
    isDemoRunning,
    demoStep,
    isDemoPaused,
    startDemo,
    stopDemo,
    pauseDemo,
    resumeDemo,
    prevDemoStep,
    nextDemoStep,
    setDemoStep,
    selectHazard,
    selectRoad,
    startSimulation,
    setWorkflowTab,
    selectObservation,
    selectPriority,
    triggerDemoWeather,
    triggerDemoSos,
    openOfficerModal,
    closeOfficerModal,
    loadRegionalWatches,
  } = useMapContext();

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const executeStep = useCallback((step: number) => {
    switch (step) {
      case 0:
        closeOfficerModal();
        setWorkflowTab('risk');
        break;
      case 1:
        closeOfficerModal();
        setWorkflowTab('risk');
        selectHazard('hz-chamoli');
        break;
      case 2:
        // Live risk evaluates automatically for Chamoli
        setWorkflowTab('risk');
        break;
      case 3:
        triggerDemoWeather();
        break;
      case 4:
        loadRegionalWatches();
        break;
      case 5:
        selectRoad('road-nh58');
        break;
      case 6:
        startSimulation('road-nh58');
        break;
      case 7:
        setWorkflowTab('impact');
        break;
      case 8:
        setWorkflowTab('priority');
        selectPriority('prio-chamoli');
        break;
      case 9:
        selectObservation('obs-chamoli-01');
        break;
      case 10:
        // Stays on observation to show community verification
        break;
      case 11:
        triggerDemoSos();
        break;
      case 12:
        // SOS panel shows shelter status
        break;
      case 13:
        // Highlight offline resilience
        break;
      case 14:
        openOfficerModal();
        break;
      case 15:
        // Stays in Officer modal showing OSINT tab or intelligence
        break;
      case 16:
        // Mass alert broadcast step
        break;
    }
  }, [
    selectHazard,
    selectRoad,
    startSimulation,
    setWorkflowTab,
    selectPriority,
    selectObservation,
    triggerDemoWeather,
    triggerDemoSos,
    openOfficerModal,
    closeOfficerModal,
    loadRegionalWatches,
  ]);

  // Execute step state change
  useEffect(() => {
    if (!isDemoRunning) return;
    executeStep(demoStep);
  }, [isDemoRunning, demoStep, executeStep]);

  // Advance demo step automatically if not paused
  useEffect(() => {
    if (!isDemoRunning || isDemoPaused) {
      if (timerRef.current) clearTimeout(timerRef.current);
      return;
    }

    if (demoStep >= DEMO_STEPS.length - 1) {
      return; // end of demo
    }

    const duration = STEP_DURATIONS[demoStep] ?? 3000;
    timerRef.current = setTimeout(() => {
      setDemoStep(demoStep + 1);
    }, duration);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isDemoRunning, isDemoPaused, demoStep, setDemoStep]);

  const currentMeta = DEMO_STEPS[demoStep] ?? DEMO_STEPS[0];
  const progressPercent = Math.round(((demoStep + 1) / DEMO_STEPS.length) * 100);

  // The launch button (shown when not running)
  if (!isDemoRunning) {
    return (
      <div className="demo-launch" aria-label="Demo Mode launcher">
        <button
          type="button"
          className="demo-launch__btn font-mono"
          onClick={startDemo}
          title="Run 17-Step Guided Judge Demonstration"
        >
          <span className="demo-launch__icon" aria-hidden="true">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          </span>
          <span className="demo-launch__label">JUDGE DEMO (17-STEP)</span>
        </button>
      </div>
    );
  }

  // Active 17-step HUD Ribbon with full navigation controls
  return (
    <div className="demo-hud" role="status" aria-live="polite" aria-label="Demo mode progress">
      <div className="demo-hud__inner">
        {/* Step details */}
        <div className="demo-hud__info">
          <div className="demo-hud__header-row">
            <span className="demo-hud__tag font-mono">
              <span className="demo-hud__tag-dot" aria-hidden="true" />
              JUDGE DEMO
            </span>
            <span className="demo-hud__phase font-mono">{currentMeta.phase}</span>
            <span className="demo-hud__counter font-mono">
              {String(demoStep + 1).padStart(2, '0')} / {DEMO_STEPS.length}
            </span>
          </div>
          <div className="demo-hud__title-row">
            <span className="demo-hud__label font-mono">{currentMeta.label}</span>
            <span className="demo-hud__desc">— {currentMeta.description}</span>
          </div>
        </div>

        {/* Step dots (compact interactive jump) */}
        <div className="demo-hud__steps" aria-label="Demo steps">
          {DEMO_STEPS.map((s) => (
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
                pauseDemo();
                setDemoStep(s.step);
              }}
              title={`Step ${s.step + 1}: ${s.label}`}
              aria-label={`Step ${s.step + 1}: ${s.label}`}
            />
          ))}
        </div>

        {/* Interactive Guided Controls */}
        <div className="demo-hud__controls">
          <button
            type="button"
            className="demo-btn font-mono"
            onClick={prevDemoStep}
            disabled={demoStep === 0}
            title="Previous Step"
          >
            ◀ PREV
          </button>

          {isDemoPaused ? (
            <button
              type="button"
              className="demo-btn demo-btn--play font-mono"
              onClick={resumeDemo}
              title="Resume Auto-Play"
            >
              ▶ PLAY
            </button>
          ) : (
            <button
              type="button"
              className="demo-btn demo-btn--pause font-mono"
              onClick={pauseDemo}
              title="Pause Auto-Play"
            >
              ⏸ PAUSE
            </button>
          )}

          <button
            type="button"
            className="demo-btn font-mono"
            onClick={nextDemoStep}
            disabled={demoStep >= DEMO_STEPS.length - 1}
            title="Next Step"
          >
            NEXT ▶
          </button>

          <button
            type="button"
            className="demo-btn demo-btn--exit font-mono"
            onClick={stopDemo}
            title="Exit Demo Mode"
          >
            ✕ EXIT
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="demo-hud__bar">
        <div
          className="demo-hud__bar-fill"
          style={{ width: `${progressPercent}%` }}
          aria-hidden="true"
        />
      </div>
    </div>
  );
}
