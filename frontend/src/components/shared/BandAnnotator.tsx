import { useState, useRef, useEffect, useLayoutEffect, useCallback } from 'react';
import { showsAPI } from '../../services/api';
import type { ShowBand, MusicBrainzArtist } from '../../types';

interface SelectionState {
  start: number;
  end: number;
  text: string;
  anchorRect: DOMRect;
}

interface BandAnnotatorProps {
  id?: string;
  eventName: string;
  bands: ShowBand[];
  onEventNameChange: (name: string) => void;
  onChange: (bands: ShowBand[]) => void;
  onBandAdded?: (artist: MusicBrainzArtist) => void;
  onBlur?: () => void;
  hasError?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function buildHTML(text: string, bands: ShowBand[]): string {
  const sorted = [...bands].sort((a, b) => a.start_pos - b.start_pos);
  let html = '';
  let cursor = 0;
  for (const band of sorted) {
    if (band.start_pos > cursor) {
      html += escapeHtml(text.slice(cursor, band.start_pos));
    }
    const bandText = escapeHtml(text.slice(band.start_pos, band.end_pos));
    html += `<span class="band-highlight" data-mbid="${band.musicbrainz_id}" data-start="${band.start_pos}" data-end="${band.end_pos}" title="${escapeHtml(band.band_name)}">${bandText}</span>`;
    cursor = band.end_pos;
  }
  if (cursor < text.length) {
    html += escapeHtml(text.slice(cursor));
  }
  return html;
}

function getCursorOffset(container: HTMLElement): number {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return 0;
  const range = sel.getRangeAt(0);
  let offset = 0;
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  let node: Node | null = walker.nextNode();
  while (node) {
    if (node === range.startContainer) {
      offset += range.startOffset;
      break;
    }
    offset += (node as Text).length;
    node = walker.nextNode();
  }
  return offset;
}

function restoreCursorOffset(container: HTMLElement, targetOffset: number): void {
  const sel = window.getSelection();
  if (!sel) return;
  let remaining = targetOffset;
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  let node: Node | null = walker.nextNode();
  while (node) {
    const len = (node as Text).length;
    if (remaining <= len) {
      const range = document.createRange();
      range.setStart(node, remaining);
      range.collapse(true);
      sel.removeAllRanges();
      sel.addRange(range);
      return;
    }
    remaining -= len;
    node = walker.nextNode();
  }
  // fallback: move to end
  const range = document.createRange();
  range.selectNodeContents(container);
  range.collapse(false);
  sel.removeAllRanges();
  sel.addRange(range);
}

function getSelectionOffsets(
  container: HTMLElement,
  selection: Selection
): { start: number; end: number } | null {
  const range = selection.getRangeAt(0);
  if (range.collapsed) return null;

  const getOffset = (node: Node, nodeOffset: number): number => {
    let total = 0;
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    let current: Node | null = walker.nextNode();
    while (current) {
      if (current === node) return total + nodeOffset;
      total += (current as Text).length;
      current = walker.nextNode();
    }
    return total + nodeOffset;
  };

  const start = getOffset(range.startContainer, range.startOffset);
  const end = getOffset(range.endContainer, range.endOffset);
  return start < end ? { start, end } : { start: end, end: start };
}

export default function BandAnnotator({
  id,
  eventName,
  bands,
  onEventNameChange,
  onChange,
  onBandAdded,
  onBlur,
  hasError,
  disabled,
}: BandAnnotatorProps) {
  const [selection, setSelection] = useState<SelectionState | null>(null);
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<MusicBrainzArtist[]>([]);
  const [pasteUrl, setPasteUrl] = useState('');
  const [pasteError, setPasteError] = useState('');
  const editableRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const isComposingRef = useRef(false);

  // Sync innerHTML when eventName or bands change from outside
  useEffect(() => {
    const el = editableRef.current;
    if (!el) return;
    const expected = buildHTML(eventName, bands);
    if (el.innerHTML !== expected) {
      const offset = getCursorOffset(el);
      el.innerHTML = expected;
      if (document.activeElement === el) {
        restoreCursorOffset(el, offset);
      }
    }
  }, [eventName, bands]);

  // Close panel on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        editableRef.current &&
        !editableRef.current.contains(e.target as Node)
      ) {
        setSelection(null);
        setResults([]);
        setPasteUrl('');
        setPasteError('');
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleInput = useCallback(() => {
    const el = editableRef.current;
    if (!el || isComposingRef.current) return;
    const newText = (el.innerText ?? el.textContent ?? '').replace(/\n/g, '');
    // Revalidate band positions — drop any that no longer fit
    const validBands = bands.filter(
      (b) =>
        b.end_pos <= newText.length &&
        newText.slice(b.start_pos, b.end_pos) === eventName.slice(b.start_pos, b.end_pos)
    );
    onEventNameChange(newText);
    if (validBands.length !== bands.length) {
      onChange(validBands);
    }
  }, [bands, eventName, onEventNameChange, onChange]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
    }
  }, []);

  const handlePaste = useCallback((e: React.ClipboardEvent<HTMLDivElement>) => {
    e.preventDefault();
    const text = e.clipboardData.getData('text/plain').replace(/\n/g, ' ');
    document.execCommand('insertText', false, text);
  }, []);

  const handleMouseUp = useCallback(async () => {
    if (disabled) return;
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !editableRef.current) return;
    if (!editableRef.current.contains(sel.anchorNode)) return;

    const offsets = getSelectionOffsets(editableRef.current, sel);
    if (!offsets) return;

    const selectedText = eventName.slice(offsets.start, offsets.end).trim();
    if (!selectedText) return;

    const overlaps = bands.some(
      (b) => offsets.start < b.end_pos && offsets.end > b.start_pos
    );
    if (overlaps) return;

    const anchorRect = sel.getRangeAt(0).getBoundingClientRect();
    setSelection({ start: offsets.start, end: offsets.end, text: selectedText, anchorRect });
    setResults([]);
    setPasteUrl('');
    setPasteError('');

    setSearching(true);
    try {
      const artists = await showsAPI.searchMusicBrainz(selectedText);
      setResults(artists);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }, [disabled, eventName, bands]);

  const addBand = (artist: MusicBrainzArtist) => {
    if (!selection) return;
    const newBand: ShowBand = {
      id: -(Date.now()),
      show_id: 0,
      musicbrainz_id: artist.id,
      band_name: artist.name,
      start_pos: selection.start,
      end_pos: selection.end,
      artist_type: artist.type ?? null,
      artist_country: artist.country ?? null,
      artist_disambiguation: artist.disambiguation ?? null,
      artist_tags: artist.tags ?? null,
    };
    onChange([...bands, newBand]);
    onBandAdded?.(artist);
    setSelection(null);
    setResults([]);
    setPasteUrl('');
    setPasteError('');
    window.getSelection()?.removeAllRanges();
  };

  const removeBand = (band: ShowBand) => {
    onChange(bands.filter((b) => b !== band));
  };

  const handlePasteUrl = async () => {
    setPasteError('');
    const mbidMatch = pasteUrl.match(
      /musicbrainz\.org\/artist\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i
    );
    if (!mbidMatch) {
      setPasteError('Could not find a MusicBrainz artist ID in that URL.');
      return;
    }
    const mbid = mbidMatch[1];
    setSearching(true);
    try {
      const artists = await showsAPI.searchMusicBrainz(selection?.text ?? '');
      const match = artists.find((a) => a.id === mbid);
      if (match) {
        addBand(match);
      } else {
        addBand({ id: mbid, name: selection?.text ?? mbid });
      }
    } catch {
      addBand({ id: mbid, name: selection?.text ?? mbid });
    } finally {
      setSearching(false);
    }
  };

  useLayoutEffect(() => {
    const el = panelRef.current;
    if (!el || !selection) return;
    const position = () => {
      const h = el.offsetHeight;
      const { anchorRect } = selection;
      const left = Math.max(8, Math.min(anchorRect.left, window.innerWidth - 420));
      const top =
        window.innerHeight - anchorRect.bottom - 8 >= h
          ? anchorRect.bottom + 8
          : Math.max(8, anchorRect.top - h - 8);
      el.style.top = `${top}px`;
      el.style.left = `${left}px`;
      el.style.visibility = 'visible';
    };
    position();
    const ro = new ResizeObserver(position);
    ro.observe(el);
    return () => ro.disconnect();
  }, [selection]);

  return (
    <div className="band-annotator">
      <div
        ref={editableRef}
        id={id}
        role="textbox"
        aria-multiline="false"
        aria-label="Event name — select text to tag a band"
        contentEditable={!disabled}
        suppressContentEditableWarning
        className={`band-annotator-text band-annotator-editable${hasError ? ' input-error' : ''}${disabled ? ' band-annotator-text--disabled' : ''}`}
        onInput={handleInput}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onMouseUp={handleMouseUp}
        onBlur={onBlur}
        onCompositionStart={() => { isComposingRef.current = true; }}
        onCompositionEnd={() => { isComposingRef.current = false; handleInput(); }}
      />

      {/* Floating search results panel */}
      {selection && (
        <div
          ref={panelRef}
          className="band-search-panel"
          style={{ position: 'fixed', zIndex: 2000, visibility: 'hidden' }}
        >
          <div className="band-search-panel__header">
            <span className="band-search-panel__query">"{selection.text}"</span>
            <button
              className="btn-close"
              onClick={() => { setSelection(null); setResults([]); }}
              aria-label="Close"
            >
              ×
            </button>
          </div>

          {searching && (
            <div className="band-search-panel__loading">Searching MusicBrainz…</div>
          )}

          {!searching && results.length === 0 && (
            <div className="band-search-panel__empty">No matches found.</div>
          )}

          {results.map((artist) => (
            <div key={artist.id} className="band-search-result">
              <div className="band-search-result__info">
                <strong className="band-search-result__name">{artist.name}</strong>
                {(artist.type || artist.country) && (
                  <span className="band-search-result__meta">
                    {[artist.type, artist.country].filter(Boolean).join(' · ')}
                  </span>
                )}
                {artist.disambiguation && (
                  <span className="band-search-result__disambiguation">
                    ({artist.disambiguation})
                  </span>
                )}
                {artist.tags && artist.tags.length > 0 && (
                  <div className="band-search-result__tags">
                    {artist.tags.slice(0, 5).map((tag) => (
                      <span key={tag} className="genre-tag">{tag}</span>
                    ))}
                  </div>
                )}
              </div>
              <div className="band-search-result__actions">
                <button
                  className="btn-primary btn-small"
                  onClick={() => addBand(artist)}
                >
                  Select
                </button>
                <a
                  href={`https://musicbrainz.org/artist/${artist.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary btn-small"
                >
                  Open ↗
                </a>
              </div>
            </div>
          ))}

          <div className="band-search-panel__paste">
            <label className="band-search-panel__paste-label">
              Paste a MusicBrainz artist URL:
            </label>
            <div className="band-search-panel__paste-row">
              <input
                type="text"
                value={pasteUrl}
                onChange={(e) => { setPasteUrl(e.target.value); setPasteError(''); }}
                placeholder="https://musicbrainz.org/artist/…"
                className="band-search-panel__paste-input"
                onKeyDown={(e) => { if (e.key === 'Enter') handlePasteUrl(); }}
              />
              <button
                className="btn-secondary btn-small"
                onClick={handlePasteUrl}
                disabled={!pasteUrl.trim()}
              >
                Use
              </button>
            </div>
            {pasteError && <div className="field-error">{pasteError}</div>}
            <a
              href={`https://musicbrainz.org/search?query=${encodeURIComponent(selection.text)}&type=artist`}
              target="_blank"
              rel="noopener noreferrer"
              className="band-search-panel__mb-link"
            >
              Search "{selection.text}" on MusicBrainz ↗
            </a>
          </div>
        </div>
      )}

      {/* Tagged bands list */}
      {bands.length > 0 && (
        <div className="band-annotator-list">
          <span className="band-annotator-list__label">Tagged artists:</span>
          {bands.map((band) => (
            <span key={band.musicbrainz_id + band.start_pos} className="band-chip">
              <a
                href={`https://musicbrainz.org/artist/${band.musicbrainz_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="band-chip__name"
              >
                {band.band_name}
              </a>
              {!disabled && (
                <button
                  type="button"
                  className="band-chip__remove"
                  onClick={() => removeBand(band)}
                  aria-label={`Remove ${band.band_name}`}
                >
                  ×
                </button>
              )}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
