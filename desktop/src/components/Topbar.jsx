import React from 'react';
import { Play, Pause, Wifi, WifiOff, ShieldCheck, ShieldAlert, Command } from 'lucide-react';
import { useMotionEase } from '../context/MotionEaseContext';
import StatusBadge from './StatusBadge';

export const Topbar = () => {
  const {
    isConnected,
    systemStatus,
    startTracking,
    pauseTracking,
    resumeEmergencyStop,
    currentPage
  } = useMotionEase();

  const pageTitles = {
    landing: 'Welcome to MotionEase',
    setup: 'Hardware & Device Configuration',
    dashboard: 'System Dashboard & Telemetry',
    studio: 'Live Multimodal Control Studio',
    calibration: '9-Point Eye Gaze Calibration',
    gestures: 'Facial Gesture Recognition',
    voice: 'Offline Speech & Command Parser',
    keyboard: 'Assistive Virtual Keyboard',
    slm: 'On-Device Small Language Model',
    settings: 'Accessibility & Signal Filtering',
    tutorial: 'Interactive User Guide & Documentation'
  };

  return (
    <header className="h-[72px] px-8 bg-bg-primary/95 backdrop-blur-md border-b border-border-color flex items-center justify-between select-none z-20">
      {/* Title */}
      <div>
        <h2 className="text-base font-bold text-txt-primary font-display">
          {pageTitles[currentPage] || 'MotionEase'}
        </h2>
        <span className="text-xs text-txt-muted flex items-center gap-2">
          <span>Batch 61 • JSS Science and Technology University</span>
        </span>
      </div>

      {/* Real-time Status and Controls */}
      <div className="flex items-center gap-3">
        {/* Safety Quick-Key Reminder Pill */}
        <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-surface-primary/80 border border-border-color text-[11px] text-txt-muted">
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded bg-surface-secondary border border-border-color font-mono text-cyan-400 font-bold">ESC</kbd>
            <span>Pause/Resume</span>
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded bg-surface-secondary border border-border-color font-mono text-red-400 font-bold">F8</kbd>
            <span>Emergency Stop</span>
          </span>
        </div>

        {/* Latency meter */}
        <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-surface-primary border border-border-color text-xs">
          <span className="text-txt-muted">Latency:</span>
          <span className="font-mono font-bold text-accent-secondary">
            {systemStatus.latency_ms.toFixed(1)} ms
          </span>
        </div>

        {/* Connection status */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-surface-primary border border-border-color text-xs">
          {isConnected ? (
            <>
              <Wifi className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400 font-medium">Local Engine</span>
            </>
          ) : (
            <>
              <WifiOff className="w-3.5 h-3.5 text-red-400" />
              <span className="text-red-400 font-medium">Reconnecting</span>
            </>
          )}
        </div>

        {/* Emergency Stop / Tracking Quick Toggle */}
        {systemStatus.emergency_stop ? (
          <button
            onClick={resumeEmergencyStop}
            className="btn-danger h-10 px-4 text-xs rounded-xl flex items-center gap-2 animate-pulse bg-red-600 hover:bg-red-500"
            title="Emergency Lock is Active. Click or press F8 to resume."
          >
            <ShieldAlert className="w-4 h-4 text-white" />
            <span>Emergency Stop Active (Press F8)</span>
          </button>
        ) : systemStatus.is_tracking ? (
          <button
            onClick={pauseTracking}
            className="btn-secondary h-10 px-3.5 text-xs rounded-xl flex items-center gap-2 hover:border-amber-400/50"
            title="Pause computer control (or press ESC anywhere)"
          >
            <Pause className="w-3.5 h-3.5 text-amber-400" />
            <span>Pause Control</span>
            <kbd className="hidden sm:inline-block px-1 py-0.2 rounded bg-surface-secondary text-[10px] text-txt-muted font-mono">ESC</kbd>
          </button>
        ) : (
          <button
            onClick={startTracking}
            className="btn-primary h-10 px-3.5 text-xs rounded-xl flex items-center gap-2"
            title="Start hands-free computer control (or press ESC anywhere)"
          >
            <Play className="w-3.5 h-3.5 text-white" />
            <span>Start Control</span>
            <kbd className="hidden sm:inline-block px-1 py-0.2 rounded bg-blue-700 text-[10px] text-blue-200 font-mono">ESC</kbd>
          </button>
        )}

        {/* Local session profile badge */}
        <div className="w-9 h-9 rounded-xl bg-surface-secondary border border-border-color flex items-center justify-center text-accent-secondary" title="Protected Offline Session (Moving physical mouse yields control)">
          <ShieldCheck className="w-5 h-5 text-emerald-400" />
        </div>
      </div>
    </header>
  );
};

export default Topbar;
