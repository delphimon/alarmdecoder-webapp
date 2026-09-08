import { type ReactNode, useEffect, useRef } from "react";

export interface ModalProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Width of the dialog. Defaults to 380px. */
  width?: number;
}

/**
 * Generic modal dialog built on the native <dialog> element.
 *
 * - Opens via showModal() so it gets the top-layer treatment and backdrop.
 * - Closes on Escape natively (browser built-in).
 * - Closes on backdrop click.
 * - Traps focus inside while open (native <dialog> behavior).
 * - Animated entry/exit using @starting-style + transition (see styles.css .modal-dialog).
 */
export function Modal({ open, title, onClose, children, width = 380 }: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open) {
      if (!dialog.open) dialog.showModal();
    } else {
      if (dialog.open) dialog.close();
    }
  }, [open]);

  // Close when the dialog fires its native 'close' event (Escape key, or programmatic close)
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const handleClose = () => onClose();
    dialog.addEventListener("close", handleClose);
    return () => dialog.removeEventListener("close", handleClose);
  }, [onClose]);

  // Close on backdrop click (click on <dialog> itself, outside the inner panel)
  const handleDialogClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) {
      dialogRef.current?.close();
    }
  };

  return (
    <dialog
      ref={dialogRef}
      className="modal-dialog"
      style={{ width }}
      onClick={handleDialogClick}
      aria-labelledby="modal-title"
    >
      <div className="modal-panel">
        <div className="modal-header">
          <h2 id="modal-title" className="modal-title">
            {title}
          </h2>
          <button type="button" className="modal-close" aria-label="Close dialog" onClick={() => dialogRef.current?.close()}>
            ✕
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </dialog>
  );
}

export interface ConfirmDialogProps {
  open: boolean;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Simple confirm dialog — native <dialog> replacement for window.confirm().
 */
export function ConfirmDialog({ open, message, confirmLabel = "Confirm", onConfirm, onCancel }: ConfirmDialogProps) {
  return (
    <Modal open={open} title="Confirm action" onClose={onCancel} width={360}>
      <p className="modal-message">{message}</p>
      <div className="modal-actions">
        <button type="button" className="btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className="btn-danger" onClick={onConfirm} autoFocus>
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
