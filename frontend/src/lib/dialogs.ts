/**
 * Modal sequencing.
 *
 * Two of this product's dialogs are raised by different clocks: the
 * identical-file warning (V-6) answers the upload, while the current-version
 * question (V-4) answers background processing that finishes on its own
 * schedule. Left alone they stack, and the one decision that changes what the
 * portfolio reads ends up buried under a notice.
 */

/** The dialog currently on top, if any other than `except`. */
function blockingDialog(except: HTMLDialogElement): HTMLDialogElement | undefined {
  const open = document.querySelectorAll<HTMLDialogElement>('dialog[open]');
  return [...open].find((dialog) => dialog !== except);
}

/**
 * Open `dialog` as soon as nothing else is open, waiting its turn if needed.
 *
 * Returns a promise that settles when the dialog is finally shown, which the
 * caller may ignore; the queueing works either way.
 */
export function openWhenFree(dialog: HTMLDialogElement): Promise<void> {
  return new Promise((resolve) => {
    const attempt = (): void => {
      const blocking = blockingDialog(dialog);
      if (!blocking) {
        dialog.showModal();
        resolve();
        return;
      }
      // Queue behind whatever is on top; a chain of dialogs drains in order.
      blocking.addEventListener('close', attempt, { once: true });
    };
    attempt();
  });
}
