import { useEffect, useRef, useState } from 'react';
import { onAirAPI } from '../../services/api';

// How long the "DJ name just changed" notice stays visible after an
// automatic changeover, in milliseconds.
const TRANSITION_NOTICE_MS = 8000;

interface UseOnAirDjResult {
  /** The currently scheduled on-air DJ name, or null if none is known. */
  currentDjName: string | null;
  /** True when `value` is non-empty and doesn't match the scheduled DJ. */
  mismatch: boolean;
  /** Set right after an automatic changeover; null otherwise. */
  transitionNotice: string | null;
  /** Dismiss the transition notice early. */
  dismissTransitionNotice: () => void;
}

/**
 * Keeps a DJ Name field in sync with the cached Spinitron on-air schedule:
 * auto-populates it when empty, flags a mismatch against who's actually
 * scheduled, and auto-advances to the next DJ (with a transient notice)
 * right when the current show ends.
 */
export function useOnAirDj(value: string, onChange: (name: string) => void): UseOnAirDjResult {
  const [currentDjName, setCurrentDjName] = useState<string | null>(null);
  const [transitionNotice, setTransitionNotice] = useState<string | null>(null);
  const changeoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const noticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const valueRef = useRef(value);
  valueRef.current = value;

  const clearChangeoverTimer = () => {
    if (changeoverTimer.current) {
      clearTimeout(changeoverTimer.current);
      changeoverTimer.current = null;
    }
  };

  const applyOnAirInfo = (info: {
    current_dj_name: string | null;
    current_show_ends_at: string | null;
    next_dj_name: string | null;
  }, isChangeover: boolean) => {
    setCurrentDjName(info.current_dj_name);

    if (isChangeover) {
      if (info.current_dj_name) {
        onChangeRef.current(info.current_dj_name);
        setTransitionNotice(`DJ name updated to ${info.current_dj_name}`);
        if (noticeTimer.current) clearTimeout(noticeTimer.current);
        noticeTimer.current = setTimeout(() => setTransitionNotice(null), TRANSITION_NOTICE_MS);
      }
    } else if (!valueRef.current.trim() && info.current_dj_name) {
      onChangeRef.current(info.current_dj_name);
    }

    clearChangeoverTimer();
    if (info.current_show_ends_at) {
      const msUntilEnd = new Date(info.current_show_ends_at).getTime() - Date.now();
      if (msUntilEnd > 0) {
        changeoverTimer.current = setTimeout(() => fetchOnAirInfo(true), msUntilEnd);
      } else {
        fetchOnAirInfo(true);
      }
    }
  };

  const fetchOnAirInfo = (isChangeover: boolean) => {
    onAirAPI
      .getCurrent()
      .then((info) => applyOnAirInfo(info, isChangeover))
      .catch(() => {});
  };

  useEffect(() => {
    fetchOnAirInfo(false);
    return () => {
      clearChangeoverTimer();
      if (noticeTimer.current) clearTimeout(noticeTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const mismatch = !!(
    value.trim() &&
    currentDjName &&
    value.trim().toLowerCase() !== currentDjName.toLowerCase()
  );

  return {
    currentDjName,
    mismatch,
    transitionNotice,
    dismissTransitionNotice: () => setTransitionNotice(null),
  };
}
