---
description: UX patterns that must be consistently applied across all scanner screens
---

# Immich Refiner UX Patterns

When building or modifying scanner screens, apply these patterns consistently.

## 1. Back to Top Button

**Component:** `BackToTop` from `components/ui/BackToTop.tsx`

**When:** All scrollable scanner screens.

```tsx
import { BackToTop } from '../../ui/BackToTop';

// Place before closing </div> of main container
<BackToTop />
```

**Currently used in:** SmartAlbumScanner, DuplicateScanner, OnThisDayScanner, MaintenanceScanner, DiscoveryScannerScreen, GeoSyncManager

---

## 2. Toast Notifications

**Component:** `ToastContainer` from `components/Toast.tsx`

**When:** Any screen with async operations (save, delete, sync).

```tsx
import { ToastContainer, type ToastMessage } from '../../Toast';

const [toasts, setToasts] = useState<ToastMessage[]>([]);
const addToast = useCallback((message: string, type: ToastMessage['type'] = 'success') => {
    setToasts(prev => [...prev, { id: Date.now().toString(), message, type }]);
}, []);
const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
}, []);

// In JSX:
<ToastContainer toasts={toasts} onDismiss={dismissToast} />
```

---

## 3. Shift+Click Range Selection

**When:** Multi-select grids or lists.

```tsx
const [lastSelectedId, setLastSelectedId] = useState<string | null>(null);

const handleToggleSelect = useCallback((id: string, isShift: boolean = false) => {
    setSelectedIds(prev => {
        const next = new Set(prev);
        if (isShift && lastSelectedId && items.length > 0) {
            const currentIndex = items.findIndex(i => i.id === id);
            const lastIndex = items.findIndex(i => i.id === lastSelectedId);
            if (currentIndex !== -1 && lastIndex !== -1) {
                const start = Math.min(currentIndex, lastIndex);
                const end = Math.max(currentIndex, lastIndex);
                for (let i = start; i <= end; i++) {
                    next.add(items[i].id);
                }
                return next;
            }
        }
        next.has(id) ? next.delete(id) : next.add(id);
        return next;
    });
    setLastSelectedId(id);
}, [lastSelectedId, items]);

// On click handler:
onClick={(e) => handleToggleSelect(item.id, e.shiftKey)}
```

---

## 4. Glassmorphic Sticky Headers

**When:** Scanner toolbars that should remain visible while scrolling.

```tsx
<div className="sticky top-0 z-30 p-4 bg-background/80 backdrop-blur-xl border-b border-border/40 shadow-sm">
    {/* Toolbar content */}
</div>
```

---

## 5. Floating Action Bars

**When:** Bulk actions on selected items.

```tsx
{selectedIds.size > 0 && (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50">
        <button className="flex items-center gap-3 px-6 py-3 bg-foreground/90 text-background backdrop-blur-md rounded-full font-semibold shadow-lg transition-all hover:scale-105 active:scale-95">
            <Save size={16} />
            Save {selectedIds.size} Changes
        </button>
    </div>
)}
```

---

## 6. Loading States

**Pattern:** Centered spinner with descriptive text.

```tsx
<div className="flex flex-col items-center justify-center h-64">
    <Loader2 className="animate-spin text-primary mb-4" size={32} />
    <p className="text-muted-foreground">Scanning library...</p>
    {loadedCount > 0 && (
        <p className="text-sm text-muted-foreground mt-2">
            {loadedCount.toLocaleString()} items scanned...
        </p>
    )}
</div>
```

---

## 7. Empty States

**Pattern:** Icon + heading + helpful suggestion.

```tsx
<div className="flex flex-col items-center justify-center flex-1 p-8">
    <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mb-4">
        <CheckCircle2 size={32} className="text-muted-foreground/50" />
    </div>
    <p className="text-lg font-medium text-foreground">No matches found</p>
    <p className="text-sm text-muted-foreground mt-1 max-w-xs text-center">
        Try adjusting your filters or scan more photos.
    </p>
</div>
```

---

## 8. Responsive Card Grids

Two patterns are used depending on the use case:

### Option A: Tailwind Breakpoints (Predictable Columns)

**When:** Fixed column counts at specific breakpoints. Use for event cards, thumbnails.

```tsx
// Discovery Events - cards stack nicely at breakpoints
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    {events.map(event => <EventCard key={event.id} {...event} />)}
</div>

// Photo thumbnails - more columns for smaller items
<div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
    {photos.map(photo => <Thumbnail key={photo.id} {...photo} />)}
</div>
```

### Option B: CSS Auto-fill (Flexible Columns)

**When:** Cards should fill available space with a minimum width. Use for pair cards (GeoSyncer).

```tsx
// GeoSyncer - pairs fill space, minimum 320px each
<div
    className="grid gap-6"
    style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}
>
    {pairs.map(pair => <PairCard key={pair.id} {...pair} />)}
</div>
```

### Which to Choose?

| Scenario | Use |
|----------|-----|
| Need exact column counts at breakpoints | Tailwind breakpoints |
| Want cards to fill space flexibly | CSS auto-fill |
| Cards have fixed aspect ratios | Tailwind breakpoints |
| Cards vary in width naturally | CSS auto-fill |

**Avoid:** JS-based column calculations with ResizeObserver—use CSS instead.

---

## Checklist for New Scanners

- [ ] `BackToTop` imported and placed
- [ ] `ToastContainer` for async feedback
- [ ] Shift+click selection (if multi-select)
- [ ] Glassmorphic sticky header
- [ ] Floating action bar (if bulk actions)
- [ ] Custom confirmation dialog (if destructive actions)
- [ ] Loading state with spinner
- [ ] Empty state with helpful message
- [ ] CSS Grid auto-fill for responsive layout

---

## 9. Confirmation Dialogs

**When:** Destructive actions (delete, trash, bulk removal).

**NEVER use:** `window.confirm()` or native browser dialogs.

**Pattern:** Custom modal with consistent styling and keyboard shortcuts.

```tsx
// State management (can be in a hook)
const [showConfirm, setShowConfirm] = useState(false);
const requestConfirmation = () => setShowConfirm(true);
const confirm = () => {
    setShowConfirm(false);
    // Perform action
};
const cancel = () => setShowConfirm(false);

// Keyboard shortcuts
useEffect(() => {
    if (!showConfirm) return;
    const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Enter') { e.preventDefault(); confirm(); }
        else if (e.key === 'Escape') { e.preventDefault(); cancel(); }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
}, [showConfirm, confirm, cancel]);

// Modal JSX
{showConfirm && (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4">
        <div className="bg-card rounded-xl shadow-2xl max-w-md w-full p-6 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center gap-3 mb-4">
                <div className="p-2 rounded-full bg-destructive/10">
                    <Trash2 className="text-destructive" size={24} />
                </div>
                <h3 className="text-lg font-semibold text-card-foreground">
                    Confirm Deletion
                </h3>
            </div>

            <p className="text-muted-foreground mb-6">
                Are you sure you want to trash <strong>{count} items</strong>?
            </p>

            <div className="flex gap-3">
                <button onClick={cancel}
                    className="flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-lg border border-input text-foreground hover:bg-accent transition-colors">
                    Cancel <kbd className="ml-1 px-1.5 py-0.5 text-xs bg-muted rounded">Esc</kbd>
                </button>
                <button onClick={confirm}
                    className="flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-destructive hover:bg-destructive/90 text-destructive-foreground font-semibold transition-colors">
                    <Trash2 size={18} /> Confirm <kbd className="ml-1 px-1.5 py-0.5 text-xs bg-black/20 rounded">Enter</kbd>
                </button>
            </div>
        </div>
    </div>
)}
```

**Key elements:**
- Fixed positioning with dark overlay (`bg-black/50`)
- Card with rounded corners and shadow
- Icon in colored circle matching action type
- Keyboard shortcuts shown as `<kbd>` elements
- Cancel (Esc) and Confirm (Enter) shortcuts
- Animate-in effect for polish

**For asset-specific deletion with merge options:** Use `ConfirmActionDialog` component.

**Currently used in:** ComparisonView (assets), MaintenanceScanner (bulk)
