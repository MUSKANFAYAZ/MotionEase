import React, { useState } from 'react';
import {
  Play,
  Pause,
  ShieldAlert,
  RotateCcw,
  Sparkles,
  Eye,
  Sliders,
  Compass,
  Smile,
  Mic,
  Activity,
  Layers,
  MousePointer,
  Keyboard,
  Zap,
  Gauge
} from 'lucide-react';
import { useMotionEase } from '../context/MotionEaseContext';
import WebcamPreview from '../components/WebcamPreview';
import HeadPoseIndicator from '../components/HeadPoseIndicator';
import ActionLog from '../components/ActionLog';
import StatusBadge from '../components/StatusBadge';
import PageHeader from '../components/PageHeader';

export const ControlStudioPage = () => {
  const {
    telemetry,
    systemStatus,
    modalities,
    actionLog,
    settings,
    updateSettings,
    startTracking,
    pauseTracking,
    triggerEmergencyStop,
    resumeEmergencyStop,
    setCurrentPage,
    calibrateNeutralHead
  } = useMotionEase();

  const [showOverlay, setShowOverlay] = useState(true);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <PageHeader
        title="Live Control Studio"
        subtitle="High-fidelity visual telemetry, real-time facial mesh overlay, and action stream."
        badge={
          <StatusBadge
            status={telemetry.face_detected ? 'active' : 'warning'}
            text={telemetry.face_detected ? 'Face Tracking Active' : 'Locating User'}
          />
        }
        actionButton={
          <div className="flex items-center gap-2">
            {systemStatus.emergency_stop ? (
              <button
                onClick={resumeEmergencyStop}
                className="btn-primary h-9 px-4 text-xs bg-emerald-600 hover:bg-emerald-500 flex items-center gap-1.5"
              >
                <span>Clear Lock (F8)</span>
              </button>
            ) : (
              <button
                onClick={triggerEmergencyStop}
                className="btn-danger h-9 px-4 text-xs flex items-center gap-1.5"
                title="Stop all computer control (F8 hotkey)"
              >
                <ShieldAlert className="w-3.5 h-3.5" />
                <span>Emergency Stop</span>
                <kbd className="px-1 py-0.2 rounded bg-red-900/60 font-mono text-[10px]">F8</kbd>
              </button>
            )}

            {systemStatus.is_tracking ? (
              <button
                onClick={pauseTracking}
                className="btn-secondary h-9 px-3 text-xs flex items-center gap-1.5 border-amber-400/40 text-amber-300 hover:border-amber-400"
                title="Pause control (ESC hotkey)"
              >
                <Pause className="w-3.5 h-3.5 text-amber-400" />
                <span>Pause</span>
                <kbd className="px-1 py-0.2 rounded bg-surface-secondary font-mono text-[10px]">ESC</kbd>
              </button>
            ) : (
              <button
                onClick={startTracking}
                className="btn-primary h-9 px-4 text-xs flex items-center gap-1.5"
                title="Resume control (ESC hotkey)"
              >
                <Play className="w-3.5 h-3.5 text-white" />
                <span>Resume Tracking</span>
                <kbd className="px-1 py-0.2 rounded bg-blue-700 font-mono text-[10px]">ESC</kbd>
              </button>
            )}
          </div>
        }
      />

      {/* Safety & User Control Banner */}
      <div className="p-3.5 rounded-2xl bg-gradient-to-r from-blue-950/40 via-surface-primary to-surface-secondary border border-accent-primary/20 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-cyan-400">
            <MousePointer className="w-3.5 h-3.5" />
          </div>
          <div>
            <span className="font-semibold text-txt-primary">Smart Touch-to-Yield Active:</span>{' '}
            <span className="text-txt-muted">
              Touching your laptop trackpad or physical mouse immediately yields control to you for 2s.
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 text-txt-muted font-mono text-[11px]">
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded bg-surface-secondary border border-border-color text-cyan-400 font-bold">ESC</kbd>
            <span>Toggle Pause</span>
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded bg-surface-secondary border border-border-color text-red-400 font-bold">F8</kbd>
            <span>Stop All</span>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Webcam Stream with Real-Time Canvas Overlay (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <WebcamPreview
            telemetry={telemetry}
            showOverlay={showOverlay}
            onToggleOverlay={() => setShowOverlay(!showOverlay)}
          />

          {/* Quick Studio Bar */}
          <div className="flex items-center justify-between p-3.5 rounded-2xl bg-surface-primary border border-border-color text-xs">
            <div className="flex items-center gap-3">
              <button
                onClick={calibrateNeutralHead}
                className="btn-secondary h-8 px-3 rounded-lg text-xs flex items-center gap-1.5 hover:border-cyan-400"
                title="Pause tracking and save the current head position as neutral"
              >
                <Compass className="w-3.5 h-3.5 text-cyan-400" />
                <span>Recenter Head</span>
              </button>

              <button
                onClick={() => setCurrentPage('calibration')}
                className="btn-secondary h-8 px-3 rounded-lg text-xs flex items-center gap-1.5 hover:border-accent-primary"
              >
                <Eye className="w-3.5 h-3.5 text-accent-primary" />
                <span>Recalibrate Gaze</span>
              </button>
            </div>

            <div className="flex items-center gap-2 font-mono text-[11px] text-txt-muted">
              <span>Loop: {systemStatus.latency_ms.toFixed(0)}ms</span>
              <span>•</span>
              <span className="text-emerald-400">{systemStatus.fps.toFixed(0)} FPS</span>
            </div>
          </div>

          {/* Head Pose Indicator Widget */}
          <HeadPoseIndicator head={telemetry.head} />
        </div>

        {/* Right Column: Telemetry Breakdown & Action Stream (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Real-time Cursor, Speed, Direction & Jitter Control Card */}
          <div className="bg-surface-primary border border-accent-primary/30 rounded-2xl p-4 space-y-3.5 shadow-lg">
            <div className="flex items-center justify-between">
              <h4 className="text-xs uppercase font-bold text-accent-secondary tracking-wider flex items-center gap-1.5">
                <Gauge className="w-4 h-4 text-accent-secondary" />
                Live Cursor & Jitter Controls
              </h4>
              <button
                onClick={() => setCurrentPage('settings')}
                className="text-[11px] text-txt-muted hover:text-cyan-400 underline"
              >
                All Settings
              </button>
            </div>

            {/* Horizontal Direction Invert Toggle */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-txt-muted block">
                Horizontal Direction (Left ↔ Right)
              </label>
              <button
                type="button"
                onClick={() => updateSettings({ invert_x: !settings.invert_x })}
                className={`w-full p-2.5 rounded-xl border text-xs font-semibold flex items-center justify-between transition-all ${
                  settings.invert_x
                    ? 'border-cyan-500/60 bg-cyan-950/30 text-cyan-300'
                    : 'border-amber-500/60 bg-amber-950/30 text-amber-300'
                }`}
                title="Click to flip horizontal cursor direction"
              >
                <div className="flex items-center gap-2">
                  <Compass className="w-4 h-4" />
                  <span>
                    {settings.invert_x
                      ? 'Looking Right → Moves Right (Inverted)'
                      : 'Looking Right → Moves Left (Raw)'}
                  </span>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded bg-surface-primary border border-border-color font-mono uppercase">
                  Click to Flip
                </span>
              </button>
            </div>

            {/* Speed / Sensitivity Controls */}
            <div className="space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <span className="text-txt-muted font-medium">Cursor Speed (Gain):</span>
                <span className="font-mono font-bold text-accent-secondary">{settings.cursor_speed.toFixed(1)}x</span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs">
                {[
                  { label: 'Slow (0.6x)', val: 0.6 },
                  { label: 'Normal (1.0x)', val: 1.0 },
                  { label: 'Fast (1.5x)', val: 1.5 }
                ].map((btn) => (
                  <button
                    key={btn.label}
                    type="button"
                    onClick={() => updateSettings({ cursor_speed: btn.val })}
                    className={`py-1.5 px-2 rounded-lg border text-center font-medium transition-all ${
                      Math.abs(settings.cursor_speed - btn.val) < 0.15
                        ? 'border-accent-primary bg-accent-primary/20 text-cyan-300 font-bold'
                        : 'border-border-color bg-surface-secondary text-txt-muted hover:border-border-color/80'
                    }`}
                  >
                    {btn.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Jitter Fixation Deadband */}
            <div className="space-y-1.5 pt-1 border-t border-border-color/50">
              <div className="flex justify-between items-center text-xs">
                <span className="text-txt-muted font-medium">Jitter Suppression (Deadband):</span>
                <span className="font-mono font-bold text-emerald-400">{settings.deadband_px} px</span>
              </div>
              <input
                type="range"
                min={3}
                max={20}
                step={1}
                value={settings.deadband_px}
                onChange={(e) => updateSettings({ deadband_px: Number(e.target.value) })}
                className="w-full accent-emerald-400 cursor-pointer h-1.5 rounded-lg bg-surface-secondary"
              />
              <div className="flex justify-between text-[10px] text-txt-muted font-mono">
                <span>More Responsive (3px)</span>
                <span>Zero Jitter / Rock Solid (20px)</span>
              </div>
            </div>

            {/* Update Frequency Toggle */}
            <div className="flex items-center justify-between pt-1 border-t border-border-color/50 text-xs">
              <span className="text-txt-muted font-medium">Cursor Frequency:</span>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => updateSettings({ cursor_rate_hz: 30 })}
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-mono border transition-all ${
                    settings.cursor_rate_hz === 30
                      ? 'border-accent-primary bg-accent-primary/20 text-cyan-300 font-bold'
                      : 'border-border-color bg-surface-secondary text-txt-muted'
                  }`}
                >
                  30 Hz
                </button>
                <button
                  type="button"
                  onClick={() => updateSettings({ cursor_rate_hz: 60 })}
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-mono border transition-all flex items-center gap-1 ${
                    settings.cursor_rate_hz === 60
                      ? 'border-emerald-400 bg-emerald-500/20 text-emerald-300 font-bold'
                      : 'border-border-color bg-surface-secondary text-txt-muted'
                  }`}
                >
                  <Zap className="w-3 h-3 text-emerald-400" />
                  <span>60 Hz Ultra</span>
                </button>
              </div>
            </div>
          </div>

          {/* Tracking Telemetry Inspection Card */}
          <div className="bg-surface-primary border border-border-color rounded-2xl p-4 space-y-3">
            <h4 className="text-xs uppercase font-bold text-txt-muted tracking-wider flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-accent-primary" />
              Tracking Telemetry Vectors
            </h4>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2.5 rounded-xl bg-surface-secondary border border-border-color/50">
                <span className="text-txt-muted block text-[11px]">Filtered Pointer (X, Y)</span>
                <span className="font-mono font-bold text-txt-primary mt-1 block">
                  {(telemetry.gaze.x * 100).toFixed(1)}%, {(telemetry.gaze.y * 100).toFixed(1)}%
                </span>
              </div>

              <div className="p-2.5 rounded-xl bg-surface-secondary border border-border-color/50">
                <span className="text-txt-muted block text-[11px]">Raw Iris Gaze (X, Y)</span>
                <span className="font-mono text-cyan-400 mt-1 block">
                  {(telemetry.gaze.raw_x * 100).toFixed(1)}%, {(telemetry.gaze.raw_y * 100).toFixed(1)}%
                </span>
              </div>

              <div className="p-2.5 rounded-xl bg-surface-secondary border border-border-color/50">
                <span className="text-txt-muted block text-[11px]">Left / Right Eye EAR</span>
                <span className="font-mono font-bold text-txt-primary mt-1 block">
                  {telemetry.gesture.left_ear.toFixed(2)} / {telemetry.gesture.right_ear.toFixed(2)}
                </span>
              </div>

              <div className="p-2.5 rounded-xl bg-surface-secondary border border-border-color/50">
                <span className="text-txt-muted block text-[11px]">Detected Gesture</span>
                <span className="font-semibold text-emerald-400 mt-1 block truncate">
                  {telemetry.gesture.detected || 'None (Neutral)'}
                </span>
              </div>
            </div>

            {/* Multimodal Modality Indicators */}
            <div className="pt-2 border-t border-border-color/50 space-y-1.5 text-xs">
              <div className="flex justify-between items-center">
                <span className="text-txt-secondary flex items-center gap-1.5">
                  <Eye className="w-3.5 h-3.5 text-accent-primary" /> Gaze Pointer Control
                </span>
                <StatusBadge status={modalities.gaze ? 'active' : 'inactive'} size="sm" />
              </div>
              <div className="flex justify-between items-center">
                <span className="text-txt-secondary flex items-center gap-1.5">
                  <Compass className="w-3.5 h-3.5 text-accent-secondary" /> Head Tilt Viewport Scrolling
                </span>
                <StatusBadge status={modalities.head ? 'active' : 'inactive'} size="sm" />
              </div>
              <div className="flex justify-between items-center">
                <span className="text-txt-secondary flex items-center gap-1.5">
                  <Smile className="w-3.5 h-3.5 text-emerald-400" /> Facial Gesture Actions
                </span>
                <StatusBadge status={modalities.gesture ? 'active' : 'inactive'} size="sm" />
              </div>
              <div className="flex justify-between items-center">
                <span className="text-txt-secondary flex items-center gap-1.5">
                  <Mic className="w-3.5 h-3.5 text-cyan-400" /> Voice Commands & Launcher
                </span>
                <StatusBadge status={modalities.voice ? 'active' : 'inactive'} size="sm" />
              </div>
            </div>
          </div>

          {/* Real-Time Action Log */}
          <ActionLog actions={actionLog} maxHeight="240px" />
        </div>
      </div>
    </div>
  );
};

export default ControlStudioPage;
