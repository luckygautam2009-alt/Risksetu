import { useMapContext, type WorkflowTab } from '../../context/MapContext';
import './WorkflowNav.css';

interface NavStep {
  id: WorkflowTab;
  stepNumber: string;
  label: string;
  badge?: string | number;
}

export function WorkflowNav() {
  const { workflowTab, setWorkflowTab, alerts, priorityList, simulationPhase } = useMapContext();

  const activeAlertsCount = alerts.filter((a) => a.status === 'ACTIVE').length;

  const STEPS: NavStep[] = [
    { id: 'risk', stepNumber: '01', label: 'RISK' },
    {
      id: 'impact',
      stepNumber: '02',
      label: 'IMPACT',
      badge: simulationPhase === 'failed' ? 'ACTIVE' : undefined,
    },
    { id: 'priority', stepNumber: '03', label: 'PRIORITY', badge: priorityList.length },
    {
      id: 'alerts',
      stepNumber: '04',
      label: 'ALERTS',
      badge: activeAlertsCount > 0 ? `${activeAlertsCount} CRITICAL` : undefined,
    },
  ];

  return (
    <nav className="wf-nav" aria-label="Continuous Intelligence Workflow">
      <div className="wf-nav__dock">
        <span className="wf-nav__title font-mono">WORKFLOW</span>
        <div className="wf-nav__steps">
          {STEPS.map((step, idx) => {
            const isActive = workflowTab === step.id;
            return (
              <div key={step.id} className="wf-nav__item">
                <button
                  type="button"
                  className={`wf-nav__btn ${isActive ? 'wf-nav__btn--active' : ''}`}
                  onClick={() => setWorkflowTab(step.id)}
                  aria-pressed={isActive}
                >
                  <span className="wf-nav__num font-mono">{step.stepNumber}</span>
                  <span className="wf-nav__label">{step.label}</span>
                  {step.badge && (
                    <span
                      className={`wf-nav__badge font-mono ${
                        step.id === 'alerts' ? 'wf-nav__badge--alert' : ''
                      }`}
                    >
                      {step.badge}
                    </span>
                  )}
                </button>
                {idx < STEPS.length - 1 && (
                  <span className="wf-nav__arrow" aria-hidden="true">
                    →
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
